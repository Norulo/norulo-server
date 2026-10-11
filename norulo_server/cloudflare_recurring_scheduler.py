"""Production-only recurrence coordination; DO state never writes a D1 heartbeat."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from .cloudflare_preview_schema import SCHEMA_OBJECTS, SCHEMA_VERSION
from .cloudflare_validation_budget import _field


RECURRING_SCHEDULER_SCOPE = "norulo-production-recurring-v1"
RECURRING_TIMEOUT_SECONDS = 10
RECURRING_QUEUE_LIMIT = 16
RECURRING_QUEUE_WAIT_SECONDS = 1
MIGRATION_NAMES = (
    "0001_ledger.sql", "0002_identity_billing_keys.sql", "0003_ledger_suggestions.sql",
    "0004_ledger_plan_usage.sql", "0005_workspaces_repositories.sql", "0006_blank_projects.sql",
    "0007_recurring_expenses_project_links.sql", "0008_workspace_join_approval.sql",
    "0009_activity_log.sql", "0010_project_removal.sql", "0011_business_erasure.sql",
    "0012_recurring_pending.sql",
)
SCHEMA_QUERY = """SELECT type,name,tbl_name,sql FROM sqlite_schema
    WHERE name NOT GLOB '_cf_*' AND tbl_name NOT GLOB '_cf_*'
    AND tbl_name <> 'd1_migrations'
    AND (name NOT GLOB 'sqlite_*' OR name GLOB 'sqlite_autoindex_*')
    ORDER BY type,name LIMIT 129"""
MIGRATION_QUERY = "SELECT name FROM d1_migrations ORDER BY id LIMIT 13"


class RecurringFailure(Exception):
    """Only bounded fixed codes are exposed; arbitrary native errors stay private."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def production_recurring_enabled(env):
    return (getattr(env, "NORULO_MODE", "") == "production"
        and str(getattr(env, "NORULO_D1_ACCESS_ENABLED", "0")) == "1"
        and str(getattr(env, "NORULO_RECURRING_EXPENSES_ENABLED", "0")) == "1")


def require_recurring_success(result):
    if _field(result, "ok", None) is not True:
        raise RuntimeError("RECURRING_EXECUTION_UNAVAILABLE")


def _integer(value):
    return type(value) is int and 0 <= value <= 9007199254740991


class RecurringJournal:
    """A single durable in-flight marker and completed UTC hour, with no reset API.

    An interrupted/uncertain attempt stays active (or stopped) forever. A later
    incarnation must not re-dispatch even when the original D1 await was canceled.
    Reconciliation is a separate future reviewed operation, never automatic.
    """
    def __init__(self, sql):
        self.sql = sql
        sql.exec("""CREATE TABLE IF NOT EXISTS norulo_recurring_scheduler (
            id INTEGER PRIMARY KEY CHECK(id=1),
            scope TEXT NOT NULL CHECK(scope='norulo-production-recurring-v1'),
            state TEXT NOT NULL CHECK(state IN ('idle','active','stopped')),
            completed_hour INTEGER NOT NULL CHECK(completed_hour>=-1),
            active_hour INTEGER,
            stopped_code TEXT,
            CHECK((state='active' AND active_hour IS NOT NULL)
                OR state<>'active')
        )""")
        if not list(sql.exec("SELECT id FROM norulo_recurring_scheduler WHERE id=1").toArray()):
            sql.exec("""INSERT INTO norulo_recurring_scheduler
                (id,scope,state,completed_hour) VALUES(1,?,'idle',-1)""", RECURRING_SCHEDULER_SCOPE)

    def snapshot(self):
        row = self.sql.exec("SELECT * FROM norulo_recurring_scheduler WHERE id=1").one()
        fields = {key: _field(row, key) for key in (
            "scope", "state", "completed_hour", "active_hour", "stopped_code")}
        if (fields["scope"] != RECURRING_SCHEDULER_SCOPE
                or fields["state"] not in {"idle", "active", "stopped"}
                or type(fields["completed_hour"]) is not int
                or not -1 <= fields["completed_hour"] <= 9007199254740991
                or fields["state"] == "active" and not _integer(fields["active_hour"])):
            raise RecurringFailure("RECURRING_STATE_INVALID")
        return fields

    def begin(self, hour):
        if not _integer(hour):
            raise RecurringFailure("RECURRING_CLOCK_INVALID")
        state = self.snapshot()
        if state["state"] != "idle":
            raise RecurringFailure("RECURRING_OUTCOME_UNKNOWN")
        if hour < state["completed_hour"]:
            raise RecurringFailure("RECURRING_CLOCK_INVALID")
        if hour == state["completed_hour"]:
            return False
        rows = list(self.sql.exec("""UPDATE norulo_recurring_scheduler
            SET state='active',active_hour=?,stopped_code=NULL
            WHERE id=1 AND state='idle' AND completed_hour<? RETURNING id""",
            float(hour), float(hour)).toArray())
        if len(rows) != 1:
            raise RecurringFailure("RECURRING_OUTCOME_UNKNOWN")
        return True

    def finish(self, hour):
        rows = list(self.sql.exec("""UPDATE norulo_recurring_scheduler
            SET state='idle',completed_hour=?,active_hour=NULL,stopped_code=NULL
            WHERE id=1 AND state='active' AND active_hour=? RETURNING id""",
            float(hour), float(hour)).toArray())
        if len(rows) != 1:
            raise RecurringFailure("RECURRING_OUTCOME_UNKNOWN")

    def stop(self, code):
        if code not in {"RECURRING_TIMEOUT", "RECURRING_OUTCOME_UNKNOWN", "RECURRING_SCHEMA_REQUIRED"}:
            raise RecurringFailure("RECURRING_STATE_INVALID")
        self.sql.exec("""UPDATE norulo_recurring_scheduler SET state='stopped',stopped_code=?
            WHERE id=1 AND state='active'""", code)


async def verify_recurring_schema(binding):
    """Read only, once per coordinator incarnation; no migration/seed/repair path."""
    if SCHEMA_VERSION != 12:
        raise RecurringFailure("RECURRING_SCHEMA_REQUIRED")
    results = await binding.batch([binding.prepare(SCHEMA_QUERY), binding.prepare(MIGRATION_QUERY)])
    schema = list(_field(results[0], "results", []))
    migrations = list(_field(results[1], "results", []))
    objects = []
    for row in schema:
        kind, name, table, sql = (_field(row, key) for key in ("type", "name", "tbl_name", "sql"))
        if (not all(type(value) is str for value in (kind, name, table))
                or not (sql is None or type(sql) is str)):
            raise RecurringFailure("RECURRING_SCHEMA_REQUIRED")
        objects.append((kind, name, table, " ".join(sql.split()) if sql else None))
    if (tuple(objects) != SCHEMA_OBJECTS
            or tuple(_field(row, "name") for row in migrations) != MIGRATION_NAMES):
        raise RecurringFailure("RECURRING_SCHEMA_REQUIRED")


class ObservedRecurringD1:
    """Preserve native atomic batches and capture all returned D1 usage metadata.

    This is observation, not an invented calendar D1 budget. first() uses all()
    because native first() discards metadata. Missing/failed/unknown outcomes
    stop the coordinator; no retry or quota refund occurs.
    """
    def __init__(self, binding):
        self.binding = binding
        self.operations = self.rows_read = self.rows_written = 0
        self.complete = True

    def prepare(self, sql):
        return _ObservedStatement(self, sql)

    async def batch(self, statements):
        statements = list(statements)
        if (not self.complete or not statements
                or any(not isinstance(item, _ObservedStatement) or item.owner is not self
                                  for item in statements)):
            raise RecurringFailure("RECURRING_OUTCOME_UNKNOWN")
        self.complete = False
        try:
            results = list(await self.binding.batch([
                self.binding.prepare(item.sql).bind(*item.params) for item in statements]))
        except asyncio.CancelledError:
            raise
        except Exception:
            # Raw constraint text must not be translated into an expected quota
            # rejection by the outer application. A failed native dispatch has
            # no complete usage evidence and cannot authorize maintenance/retry.
            raise RecurringFailure("RECURRING_OUTCOME_UNKNOWN") from None
        if len(results) != len(statements):
            raise RecurringFailure("RECURRING_OUTCOME_UNKNOWN")
        self.operations += len(statements)
        for result in results:
            meta = _field(result, "meta", None)
            reads, writes = _field(meta, "rows_read", None), _field(meta, "rows_written", None)
            if _field(result, "success", None) is not True or not _integer(reads) or not _integer(writes):
                raise RecurringFailure("RECURRING_OUTCOME_UNKNOWN")
            self.rows_read += reads
            self.rows_written += writes
        self.complete = True
        return results

    def metrics(self):
        return {"operations": self.operations, "rowsRead": self.rows_read,
            "rowsWritten": self.rows_written, "complete": self.complete}


@dataclass(frozen=True)
class _ObservedStatement:
    owner: ObservedRecurringD1
    sql: str
    params: tuple = ()

    def bind(self, *params):
        return _ObservedStatement(self.owner, self.sql, params)

    async def all(self):
        return (await self.owner.batch([self]))[0]

    async def run(self):
        return await self.all()

    async def first(self, column=None):
        rows = _field(await self.all(), "results", [])
        row = rows[0] if rows else None
        return _field(row, column) if column is not None and row is not None else row

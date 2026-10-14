"""Production-only recurrence coordination; DO state never writes a D1 heartbeat."""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import time
from dataclasses import dataclass

from .cloudflare_preview_schema import SCHEMA_OBJECTS, SCHEMA_VERSION
from .cloudflare_validation_budget import _field


RECURRING_SCHEDULER_SCOPE = "norulo-production-recurring-v1"
PRODUCTION_RECURRING_CRON = "10 16 * * *"  # Daily 00:10 Asia/Shanghai; Cloudflare cron uses UTC.
RECURRING_TIMEOUT_SECONDS = 10
RECURRING_QUEUE_LIMIT = 16
RECURRING_QUEUE_WAIT_SECONDS = 1
OWNER_PARALLELISM = 8
OWNER_PAGE_SIZE = 64
MAX_SELECTED_OWNERS = 5000
MAX_DAILY_OCCURRENCES = 10000
MAX_OWNER_RPCS = 8192
MAX_OWNER_CHUNK_OCCURRENCES = 20
MAX_OWNER_NATIVE_SQL = 800
ROOT_SOFT_SECONDS = 600
OWNER_SOFT_SECONDS = 120
# Leave enough room for a whole occurrence, including all authority/quota reads
# and its indivisible financial batch. The dispatch guard remains authoritative.
OCCURRENCE_SQL_RESERVE = 200
MIGRATION_NAMES = (
    "0001_ledger.sql", "0002_identity_billing_keys.sql", "0003_ledger_suggestions.sql",
    "0004_ledger_plan_usage.sql", "0005_workspaces_repositories.sql", "0006_blank_projects.sql",
    "0007_recurring_expenses_project_links.sql", "0008_workspace_join_approval.sql",
    "0009_activity_log.sql", "0010_project_removal.sql", "0011_business_erasure.sql",
    "0012_recurring_pending.sql", "0013_export_key_indexes.sql", "0014_expense_last_source.sql", "0015_jev_trial_calls.sql",
)
SCHEMA_QUERY = """SELECT type,name,tbl_name,sql FROM sqlite_schema
    WHERE name NOT GLOB '_cf_*' AND tbl_name NOT GLOB '_cf_*'
    AND tbl_name <> 'd1_migrations'
    AND (name NOT GLOB 'sqlite_*' OR name GLOB 'sqlite_autoindex_*')
    ORDER BY type,name LIMIT 129"""
MIGRATION_QUERY = "SELECT name FROM d1_migrations ORDER BY id LIMIT 16"


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


def _log_number(value):
    if (type(value) not in {int, float} or not 0 <= value <= 9007199254740991
            or not math.isfinite(value) or int(value) != value):
        return None
    return int(value)


def recurring_log_receipts(phase, *, result=None, scheduled_time=None):
    """Project fixed diagnostics only; never serialize a result or exception."""
    code, terminal = {
        "started": ("NORULO_RECURRING_STARTED", "started"),
        "returned": ("NORULO_RECURRING_COMPLETED", "completed"),
        "exception": ("NORULO_RECURRING_FAILED", "failed"),
        "cancelled": ("NORULO_RECURRING_CANCELLED", "cancelled"),
    }[phase]
    payload = {"code": code, "phase": terminal, "status": phase, "healthy": False}
    scheduled = _log_number(scheduled_time)
    if scheduled is not None:
        payload["scheduledTime"] = scheduled  # UTC event milliseconds, not a business clock.
    if phase in {"started", "cancelled"}:
        return [("error" if phase == "cancelled" else "log", payload)]
    counts = ("scanned", "created", "blocked", "replayed", "selectedOwners",
              "failedOwners", "ownerRpcs")
    try:
        values = {key: _log_number(_field(result, key)) for key in counts}
        payload.update({key: value for key, value in values.items() if value is not None})
        metrics = _field(result, "metrics")
        numeric_metrics = {key: _log_number(_field(metrics, key))
                           for key in ("operations", "rowsRead", "rowsWritten")}
        payload.update({key: value for key, value in numeric_metrics.items() if value is not None})
        complete = _field(metrics, "complete")
        if type(complete) is bool:
            payload["metricsComplete"] = complete
        ok, skipped, backlog = (_field(result, key) for key in ("ok", "skipped", "backlog"))
        if type(backlog) is bool:
            payload["backlog"] = backlog
        error = _field(result, "error")
        not_completed = ({"RECURRING_BUSY": "busy", "RECURRING_DISABLED": "disabled"}
                         .get(error) if type(error) is str else None)
        if phase == "exception" and result is None:
            payload.update(code="NORULO_RECURRING_FAILED", status="exception")
        elif ok is not True:
            payload.update(code="NORULO_RECURRING_NOT_COMPLETED" if not_completed
                           else "NORULO_RECURRING_FAILED",
                           status=not_completed or "result_rejected")
        elif phase == "exception":
            payload.update(code="NORULO_RECURRING_FAILED", status="exception")
        elif values["failedOwners"] is not None and values["failedOwners"] > 0:
            payload.update(code="NORULO_RECURRING_FAILED", status="failed_owners")
        elif complete is not True:
            payload.update(code="NORULO_RECURRING_FAILED", status="metrics_incomplete")
        elif skipped is True:
            # Root's legacy skip receipt omits the fanout fields. Accept only
            # the actual zero-work shape, never a forged skip hiding activity.
            if (all(values[key] == 0 for key in counts[:4])
                    and all(value == 0 for value in numeric_metrics.values())
                    and all(_field(result, key) is None or values[key] == 0 for key in counts[4:])
                    and (backlog is None or backlog is False)):
                payload["status"] = "skipped"
            else:
                payload.update(code="NORULO_RECURRING_FAILED", status="invalid_result")
        elif (skipped is not None and skipped is not False or type(backlog) is not bool
                or any(value is None for value in values.values())
                or any(value is None for value in numeric_metrics.values())):
            payload.update(code="NORULO_RECURRING_FAILED", status="invalid_result")
        else:
            warning = backlog or values["blocked"] > 0
            payload.update(status="warning" if warning else "healthy", healthy=not warning)
    except BaseException:
        payload.update(code="NORULO_RECURRING_FAILED", status="invalid_result")
        return [("error", payload)]
    severity = "error" if payload["code"] != "NORULO_RECURRING_COMPLETED" else (
        "warn" if payload["status"] == "warning" else "log")
    receipts = [(severity, payload)]
    if phase == "returned":
        for present, warning_code, status in (
                (backlog is True, "NORULO_RECURRING_BACKLOG", "backlog"),
                (values["blocked"] is not None and values["blocked"] > 0,
                 "NORULO_RECURRING_BLOCKED", "blocked")):
            if present:
                receipts.append(("warn", {**payload, "code": warning_code,
                    "phase": "warning", "status": status, "healthy": False}))
    return receipts


def log_recurring_receipt(phase, *, result=None, scheduled_time=None):
    """Best-effort JS console levels; logging cannot alter finance or cancellation."""
    try:
        for severity, payload in recurring_log_receipts(phase, result=result,
                scheduled_time=scheduled_time):
            message = json.dumps(payload, separators=(",", ":"), allow_nan=False)
            try:
                from js import console
                getattr(console, severity)(message)
            except BaseException:
                try:
                    print(message)
                except BaseException:
                    pass
    except BaseException:
        pass


def _integer(value):
    return type(value) is int and 0 <= value <= 9007199254740991


def server_now():
    value = time.time()
    if type(value) not in {int, float} or not math.isfinite(value) or not 0 <= value <= 9007199254740991:
        raise RecurringFailure("RECURRING_CLOCK_INVALID")
    return int(value)


def daily_epoch(now):
    return ((now - 58200) // 86400) * 86400 + 58200


def rpc_integer(value):
    # SDK RPC numbers can arrive as int or float; bool/NaN/unsafe values cannot.
    if type(value) not in {int, float} or not math.isfinite(value) or value != int(value) or not 0 <= value <= 9007199254740991:
        raise RecurringFailure("RECURRING_INPUT_INVALID")
    return int(value)


def owner_scope(owner):
    from .cloudflare_ledger_api import _valid_resource_id
    if not _valid_resource_id(owner):
        raise RecurringFailure("RECURRING_INPUT_INVALID")
    return RECURRING_SCHEDULER_SCOPE + ":owner:" + hashlib.sha256(owner.encode("utf-8")).hexdigest()


def require_role(ctx, env, owner=None):
    namespace = getattr(env, "RECURRING_SCHEDULER", None)
    scope = RECURRING_SCHEDULER_SCOPE if owner is None else owner_scope(owner)
    if namespace is None:
        raise RecurringFailure("RECURRING_ROLE_INVALID")
    actual, expected = ctx.id, namespace.idFromName(scope)
    def text_id(value):
        stringify = getattr(value, "toString", None)
        return str(stringify()) if callable(stringify) else str(value)
    if text_id(actual) != text_id(expected):
        raise RecurringFailure("RECURRING_ROLE_INVALID")


class DispatchJournal:
    """One bounded mutable JSON row per root/Owner object; no append-only log.

    The legacy root journal remains authoritative. Owner identity never changes
    with the epoch, so an active/stopped outcome cannot be bypassed tomorrow.
    """
    def __init__(self, sql, identity):
        self.sql, self.identity = sql, identity
        sql.exec("""CREATE TABLE IF NOT EXISTS norulo_recurring_dispatch (
            id INTEGER PRIMARY KEY CHECK(id=1), identity TEXT NOT NULL,
            payload TEXT NOT NULL CHECK(length(payload)<=32768))""")

    def read(self):
        rows = list(self.sql.exec("SELECT identity,payload FROM norulo_recurring_dispatch WHERE id=1").toArray())
        if not rows:
            return None
        if len(rows) != 1 or _field(rows[0], "identity") != self.identity:
            raise RecurringFailure("RECURRING_STATE_INVALID")
        try:
            raw = _field(rows[0], "payload")
            if type(raw) is not str or len(raw) > 32768:
                raise ValueError()
            result = json.loads(raw)
            if type(result) is not dict:
                raise ValueError()
            return result
        except Exception:
            raise RecurringFailure("RECURRING_STATE_INVALID") from None

    def write(self, value):
        encoded = json.dumps(value, separators=(",", ":"), allow_nan=False)
        if len(encoded) > 32768:
            raise RecurringFailure("RECURRING_STATE_INVALID")
        rows = list(self.sql.exec("""INSERT INTO norulo_recurring_dispatch(id,identity,payload)
            VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload
            WHERE norulo_recurring_dispatch.id=1 AND norulo_recurring_dispatch.identity=excluded.identity
            RETURNING id""", self.identity, encoded).toArray())
        if len(rows) != 1:
            raise RecurringFailure("RECURRING_OUTCOME_UNKNOWN")


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
    if SCHEMA_VERSION != 15:
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
    def __init__(self, binding, *, query_limit=None):
        self.binding = binding
        if query_limit is not None and (type(query_limit) is not int or query_limit < 1):
            raise ValueError("recurring query limit")
        self.query_limit = query_limit
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
        if self.query_limit is not None and self.operations + len(statements) > self.query_limit:
            # No partial batch is ever sent. The normal caller reserves space
            # at occurrence boundaries; exceeding that reserve is conservative
            # failure, not permission to replay a partially handled occurrence.
            raise RecurringFailure("RECURRING_SQL_LIMIT")
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


DUE_PREDICATE = """(status='active' OR (status='blocked' AND blocked_code IN
    ('RECORD_LIMIT','RETENTION_CLEANUP_REQUIRED','RETENTION_TARGET_FORBIDDEN','CATCHUP_REVIEW_REQUIRED')))
    AND next_run_at<=?"""


def empty_counts():
    return {"scanned": 0, "created": 0, "blocked": 0, "replayed": 0}


def validate_owner_state(state, owner):
    if (type(state) is not dict or state.get("owner") != owner
            or state.get("state") not in {"ready", "complete", "active", "stopped"}
            or not _integer(state.get("epoch")) or not _integer(state.get("nextChunk"))
            or state["nextChunk"] > 8192 or not _integer(state.get("cursor"))
            or type(state.get("catchup")) is not dict):
        raise RecurringFailure("RECURRING_STATE_INVALID")
    rules = state.get("rules")
    if rules is None:
        if state["cursor"] != 0 or state["catchup"]:
            raise RecurringFailure("RECURRING_STATE_INVALID")
        return
    if type(rules) is not list or len(rules) > 100 or state["cursor"] > len(rules):
        raise RecurringFailure("RECURRING_STATE_INVALID")
    for identifier in rules:
        owner_scope(identifier)
    if rules != sorted(set(rules)) or any(key not in rules or type(value) is not int
            or not 0 <= value <= 3 for key, value in state["catchup"].items()):
        raise RecurringFailure("RECURRING_STATE_INVALID")


def add_metrics(total, value):
    if type(_field(value, "complete")) is not bool:
        raise RecurringFailure("RECURRING_OUTCOME_UNKNOWN")
    for key in ("operations", "rowsRead", "rowsWritten"):
        number = _field(value, key)
        if not _integer(number) or total[key] + number > 9007199254740991:
            raise RecurringFailure("RECURRING_OUTCOME_UNKNOWN")
        total[key] += number
    total["complete"] = total["complete"] and _field(value, "complete") is True


async def execute_owner_chunk(*, env, observed, state, policy, gateway, email_gateway, clock):
    """Process only this Owner's snapshot; every occurrence keeps its own batch.

    The caller has already persisted active. This function never clears it; a
    lost response or interruption cannot authorize replay of an unknown batch.
    """
    from .cloudflare_ledger_recurring import (
        _VISIBLE_TARGET, _recover_legacy_block, generate_occurrence, LEGACY_RECOVERY_CODES,
    )
    from .cloudflare_plan_limits import PlanLimitedD1, PlanLimitError
    counts = empty_counts()
    owner, cutoff = state["owner"], state["epoch"]
    if state["rules"] is None:
        rows = _field(await observed.prepare("SELECT id FROM expense_recurring_rules WHERE owner_id=? AND "
            + DUE_PREDICATE + " AND " + _VISIBLE_TARGET + " ORDER BY id LIMIT 101").bind(owner, cutoff).all(), "results", [])
        state["rules"] = [_field(row, "id") for row in rows]
        if (len(state["rules"]) > 100 or any(owner_scope(identifier) is None for identifier in state["rules"])
                or len(set(state["rules"])) != len(state["rules"])):
            raise RecurringFailure("RECURRING_STATE_INVALID")
    started = time.monotonic()
    handled = 0
    deferred = False
    retry_at = 0
    while state["cursor"] < len(state["rules"]):
        if (handled >= MAX_OWNER_CHUNK_OCCURRENCES
                or time.monotonic() - started >= OWNER_SOFT_SECONDS
                or observed.operations + OCCURRENCE_SQL_RESERVE > MAX_OWNER_NATIVE_SQL):
            break
        identifier = state["rules"][state["cursor"]]
        if state["catchup"].get(identifier, 0) >= 3:
            state["cursor"] += 1
            continue
        now = clock()
        application = PlanLimitedD1(observed, now=now, policy=policy)
        application.email_gateway = observed.email_gateway = email_gateway
        row = await observed.prepare("SELECT * FROM expense_recurring_rules WHERE owner_id=? AND id=? AND "
            + _VISIBLE_TARGET).bind(owner, identifier).first()
        if state["catchup"].get(identifier, 0) == 0:
            counts["scanned"] += 1
        if (row is None or row["revision"] >= 9007199254740991
                or row["next_run_at"] is None or row["next_run_at"] > cutoff):
            state["cursor"] += 1
            continue
        if row["status"] == "blocked":
            if row["blocked_code"] not in LEGACY_RECOVERY_CODES:
                state["cursor"] += 1
                continue
            row = await _recover_legacy_block(application, observed, gateway, row, now)
            if row["status"] != "active":
                counts["blocked"] += 1
                handled += 1
                state["cursor"] += 1
                continue
        if row["status"] != "active":
            state["cursor"] += 1
            continue
        try:
            row, outcome = await generate_occurrence(binding=application, maintenance_binding=observed,
                gateway=gateway, row=row, now=now, yield_on_rate_limit=True)
        except PlanLimitError as error:
            if error.code != "WRITE_RATE_LIMIT" or observed.complete is not True:
                raise
            # Only a known pre-dispatch rejection reaches here. There is no
            # rule/pointer mutation, no D1 heartbeat and no automatic refund.
            deferred, retry_at = True, (clock() // 60 + 1) * 60
            break
        if outcome is None:
            state["cursor"] += 1
            continue
        if outcome not in {"created", "blocked", "replayed"}:
            raise RecurringFailure("RECURRING_OUTCOME_UNKNOWN")
        counts[outcome] += 1
        handled += 1
        state["catchup"][identifier] = state["catchup"].get(identifier, 0) + 1
        if (row["status"] != "active" or row["next_run_at"] is None
                or row["next_run_at"] > cutoff or state["catchup"][identifier] >= 3):
            state["cursor"] += 1
    complete = state["cursor"] == len(state["rules"])
    return {"ok": True, "complete": complete, "deferred": deferred,
        "retryAt": retry_at, "nextChunk": state["nextChunk"] + 1,
        **counts, "metrics": observed.metrics()}


def validate_owner_result(result, expected):
    if (_field(result, "ok") is not True or type(_field(result, "complete")) is not bool
            or type(_field(result, "deferred")) is not bool
            or not _integer(_field(result, "nextChunk")) or _field(result, "nextChunk") != expected + 1
            or not _integer(_field(result, "retryAt"))):
        raise RecurringFailure("RECURRING_OUTCOME_UNKNOWN")
    counts = {key: _field(result, key) for key in empty_counts()}
    if (any(not _integer(value) for value in counts.values()) or counts["scanned"] > 100
            or sum(counts[key] for key in ("created", "blocked", "replayed")) > MAX_OWNER_CHUNK_OCCURRENCES
            or _field(_field(result, "metrics"), "complete") is not True
            or _field(_field(result, "metrics"), "operations", MAX_OWNER_NATIVE_SQL + 1) > MAX_OWNER_NATIVE_SQL):
        raise RecurringFailure("RECURRING_OUTCOME_UNKNOWN")
    return counts


async def drain_owners(*, env, observed, epoch, clock, previous=None):
    """Eight Owner loops, bounded deferred pool, keyset discovery and no replay.

    Known minute yields release worker slots. Discovery continues before sleeping
    for deferred jobs; a few quota-limited Owners cannot hold every ready Owner.
    """
    from .cloudflare_ledger_recurring import _VISIBLE_TARGET
    namespace = env.RECURRING_SCHEDULER
    counts = empty_counts()
    metrics = {"operations": 0, "rowsRead": 0, "rowsWritten": 0, "complete": True}
    selected = failed = rpc_calls = handled = reserved = 0
    backlog = False
    unresolved_transport = False
    previous = previous or {}
    cursor = previous.get("cursor", "")
    carry = previous.get("pending", [])
    if (type(cursor) is not str or cursor and not owner_scope(cursor)
            or type(carry) is not list or len(carry) > OWNER_PAGE_SIZE
            or len(set(carry)) != len(carry)):
        raise RecurringFailure("RECURRING_STATE_INVALID")
    for owner in carry:
        owner_scope(owner)
    carry_owners = set(carry)
    deferred, unfinished = [], []
    settled = asyncio.Event()
    exhausted = False
    capped = False
    started = time.monotonic()
    def may_launch():
        return (not unresolved_transport and time.monotonic() - started < ROOT_SOFT_SECONDS and rpc_calls < MAX_OWNER_RPCS
            and handled + reserved + MAX_OWNER_CHUNK_OCCURRENCES <= MAX_DAILY_OCCURRENCES)
    while may_launch():
        page = []
        if carry:
            page, carry = [(owner, 0, 0) for owner in carry], []
            selected += len(page)
        elif not exhausted and selected < MAX_SELECTED_OWNERS and len(deferred) < OWNER_PAGE_SIZE:
            room = min(OWNER_PAGE_SIZE - len(deferred), MAX_SELECTED_OWNERS - selected)
            rows = _field(await observed.prepare("SELECT DISTINCT owner_id FROM expense_recurring_rules WHERE owner_id>? AND "
                + DUE_PREDICATE + " AND " + _VISIBLE_TARGET + " ORDER BY owner_id LIMIT ?").bind(
                    cursor, epoch, room).all(), "results", [])
            raw_owners = [_field(row, "owner_id") for row in rows]
            if raw_owners != sorted(set(raw_owners)) or any(owner <= cursor for owner in raw_owners):
                raise RecurringFailure("RECURRING_OUTCOME_UNKNOWN")
            for owner in raw_owners:
                owner_scope(owner)
            if raw_owners:
                cursor = raw_owners[-1]
            if len(raw_owners) < room:
                exhausted, cursor = True, ""
            owners = [owner for owner in raw_owners if owner not in carry_owners]
            page = [(owner, 0, 0) for owner in owners]
            selected += len(page)
        else:
            capped = not exhausted and selected >= MAX_SELECTED_OWNERS
        if not page:
            if not exhausted and not capped and len(deferred) < OWNER_PAGE_SIZE:
                continue  # A keyset page can contain only already-carried Owners.
            if not deferred:
                backlog = capped
                break
            retry = min(item[2] for item in deferred)
            delay = max(0, retry - clock())
            if time.monotonic() - started + delay >= ROOT_SOFT_SECONDS:
                backlog = True
                break
            # Only known quota denials wait. There are no active child RPCs,
            # SQL polls, D1 heartbeats, commercial refunds or unknown retries.
            if delay:
                await asyncio.sleep(delay)
            page = [item for item in deferred if item[2] <= clock()]
            deferred = [item for item in deferred if item[2] > clock()]
            if not page:
                # A rolled-back business clock cannot produce an infinite wait.
                backlog = True
                break
        jobs = asyncio.Queue()
        for item in page:
            jobs.put_nowait(item)
        async def worker():
            nonlocal failed, rpc_calls, handled, reserved, backlog, unresolved_transport
            while not jobs.empty():
                owner, sequence, retry_at = jobs.get_nowait()
                if not may_launch():
                    if (reserved and not unresolved_transport
                            and time.monotonic() - started < ROOT_SOFT_SECONDS
                            and rpc_calls < MAX_OWNER_RPCS
                            and handled + MAX_OWNER_CHUNK_OCCURRENCES <= MAX_DAILY_OCCURRENCES):
                        jobs.put_nowait((owner, sequence, retry_at))
                        settled.clear()
                        await settled.wait()
                        continue
                    unfinished.append(owner)
                    backlog = True
                    return
                rpc_calls += 1  # Includes every run and read-only progress RPC.
                reserved += MAX_OWNER_CHUNK_OCCURRENCES
                recovered_transport = False
                try:
                    try:
                        stub = namespace.get(namespace.idFromName(owner_scope(owner)))
                    except Exception:
                        unresolved_transport = True
                        raise
                    try:
                        result = await stub.runOwnerChunk(owner, float(epoch), float(sequence))
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        try:
                            if rpc_calls >= MAX_OWNER_RPCS:
                                raise RecurringFailure("RECURRING_OUTCOME_UNKNOWN")
                            rpc_calls += 1
                            progress = await stub.ownerProgress(owner, float(epoch))
                            if (_field(progress, "ok") is not True or _field(progress, "state") not in {"ready", "complete"}
                                    or not _integer(_field(progress, "nextChunk"))
                                    or _field(progress, "nextChunk") != sequence + 1):
                                raise RecurringFailure("RECURRING_OUTCOME_UNKNOWN")
                            result = _field(progress, "result")
                            recovered_transport = True
                        except BaseException:
                            unresolved_transport = True
                            raise
                    # Even a stopped Owner's known earlier metadata is retained.
                    # Missing response/metadata remains explicitly incomplete.
                    add_metrics(metrics, _field(result, "metrics"))
                    current = validate_owner_result(result, sequence)
                    for key in counts:
                        counts[key] += current[key]
                    handled += sum(current[key] for key in ("created", "blocked", "replayed"))
                    if not _field(result, "complete"):
                        job = (owner, sequence + 1, _field(result, "retryAt"))
                        if _field(result, "deferred"):
                            deferred.append(job)
                        else:
                            jobs.put_nowait(job)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    if recovered_transport:
                        unresolved_transport = True
                    failed += 1
                    # Retain the entire uncertain engineering reservation. Only
                    # a known result can reclaim unused occurrence slots.
                    handled += MAX_OWNER_CHUNK_OCCURRENCES
                    metrics["complete"] = False
                finally:
                    reserved -= MAX_OWNER_CHUNK_OCCURRENCES
                    settled.set()
        # Await all launched children. One Owner failure never cancels siblings.
        await asyncio.gather(*(worker() for _ in range(OWNER_PARALLELISM)))
        while not jobs.empty():
            unfinished.append(jobs.get_nowait()[0])
        if backlog:
            break
    if not may_launch():
        backlog = True
    pending = list(dict.fromkeys(unfinished + [item[0] for item in deferred] + carry))
    if len(pending) > OWNER_PAGE_SIZE:
        raise RecurringFailure("RECURRING_STATE_INVALID")
    add_metrics(metrics, observed.metrics())
    if unresolved_transport:
        # All already-launched siblings have settled above. A failed progress
        # lookup cannot create a durable Owner quarantine, so retain the legacy
        # root unknown-stop instead of making an unproved isolation claim.
        failure = RecurringFailure("RECURRING_OUTCOME_UNKNOWN")
        failure.metrics, failure.counts = metrics, counts
        raise failure
    return {"ok": True, **counts, "selectedOwners": selected, "failedOwners": failed,
        "backlog": backlog, "ownerRpcs": rpc_calls, "metrics": metrics,
        "checkpoint": {"cursor": cursor, "pending": pending}}

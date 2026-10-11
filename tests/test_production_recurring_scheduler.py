"""Production entry/DO contracts using SQLite only; metadata here is simulated.

These fixtures exercise SQL atomicity and application fences, not Cloudflare
billing. Real native rows_read/rows_written are a separate Workerd acceptance.
"""
import asyncio
import json
import sqlite3
from types import SimpleNamespace

import pytest

from norulo_server.cloudflare_recurring_scheduler import (
    MIGRATION_NAMES, PRODUCTION_RECURRING_CRON, RECURRING_SCHEDULER_SCOPE, RecurringJournal,
    owner_scope, daily_epoch,
)
from norulo_server.cloudflare_state_records import encode_record, record_name
from test_d1_validation_budget import LocalSql
from test_ledger_recurring import app, NOW, NoGitHub, create, draft, legacy_due
from test_worker_production_runtime import load_entry, NoPreviewEnvironment


ENABLED = {"NORULO_MODE": "production", "NORULO_D1_ACCESS_ENABLED": "1",
    "NORULO_RECURRING_EXPENSES_ENABLED": "1"}


class NoEffects(SimpleNamespace):
    def __getattr__(self, name):
        raise AssertionError("Unexpected access: " + name)


class LocalPrepared:
    def __init__(self, owner, sql, params=()):
        self.owner, self.sql, self.params = owner, sql, params

    def bind(self, *params):
        return LocalPrepared(self.owner, self.sql, params)


class LocalNativeD1:
    """Native-shaped local atomic execution. Usage is SQLite-only simulation."""
    def __init__(self, store):
        self.store, self.dispatched, self.local_changes = store, [], 0
        self.entered = self.release = self.failure = self.after_commit = None
        self.metadata = True

    def prepare(self, sql):
        return LocalPrepared(self, sql)

    async def batch(self, statements):
        statements = list(statements)
        self.dispatched.append([(item.sql, item.params) for item in statements])
        if self.entered is not None:
            self.entered.set()
            await self.release.wait()
        if self.failure is not None:
            raise self.failure
        results = []
        with self.store._immediate() as db:
            for item in statements:
                before = db.total_changes
                cursor = db.execute(item.sql, item.params)
                rows = [dict(row) for row in cursor.fetchall()] if cursor.description else []
                changed = db.total_changes - before
                self.local_changes += changed
                result = SimpleNamespace(success=True, results=rows)
                if self.metadata:
                    result.meta = SimpleNamespace(rows_read=len(rows), rows_written=changed)
                results.append(result)
        if self.after_commit is not None:
            self.after_commit()
        return results


@pytest.fixture
def production(app, monkeypatch):
    entry = load_entry()
    clock = [NOW]
    monkeypatch.setattr(entry.time, "time", lambda: clock[0])
    monkeypatch.setattr(entry, "WorkerGitHubGateway", lambda _: NoGitHub())
    with app.store._immediate() as db:
        db.execute("CREATE TABLE d1_migrations(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE)")
        db.executemany("INSERT INTO d1_migrations(name) VALUES(?)", [(name,) for name in MIGRATION_NAMES])
    raw = LocalNativeD1(app.store)
    env = NoPreviewEnvironment(**ENABLED, DB=raw, NORULO_EMAIL_AUTH_ENABLED="0")
    connection = sqlite3.connect(":memory:")
    sql = LocalSql(connection)
    ctx = SimpleNamespace(id=RECURRING_SCHEDULER_SCOPE, storage=SimpleNamespace(sql=sql))
    coordinator = entry.RecurringScheduler(ctx, env)
    owners, connections = {}, []
    def get(identity):
        if identity == RECURRING_SCHEDULER_SCOPE:
            return coordinator
        if identity not in owners:
            connection = sqlite3.connect(":memory:")
            connections.append(connection)
            owner_ctx = SimpleNamespace(id=identity, storage=SimpleNamespace(sql=LocalSql(connection)))
            owners[identity] = entry.RecurringScheduler(owner_ctx, env)
        return owners[identity]
    env.RECURRING_SCHEDULER = SimpleNamespace(idFromName=lambda name: name, get=get)
    try:
        yield SimpleNamespace(entry=entry, coordinator=coordinator, ctx=ctx, env=env,
            app=app, raw=raw, clock=clock, monkeypatch=monkeypatch, owners=owners)
    finally:
        for item in connections:
            item.close()
        connection.close()


@pytest.mark.parametrize("field,value", [
    ("NORULO_MODE", "preview"), ("NORULO_MODE", "local"), ("NORULO_MODE", "Production"),
    ("NORULO_D1_ACCESS_ENABLED", "0"), ("NORULO_D1_ACCESS_ENABLED", "true"),
    ("NORULO_RECURRING_EXPENSES_ENABLED", "0"), ("NORULO_RECURRING_EXPENSES_ENABLED", "true"),
])
def test_disabled_rpc_has_no_storage_d1_or_provider_side_effects(field, value):
    entry = load_entry()
    scheduler = entry.RecurringScheduler(NoEffects(), NoEffects(**{**ENABLED, field: value}))
    assert asyncio.run(scheduler.runRecurring()) == {"ok": False, "error": "RECURRING_DISABLED"}
    assert scheduler.journal is None and scheduler._waiting == 0


def test_production_scheduled_dispatches_only_fixed_namespace_with_no_rpc_clock():
    entry = load_entry()
    calls = []
    async def tick(*args, **kwargs):
        assert not args and not kwargs
        calls.append("completed")
        return {"ok": True}
    namespace = SimpleNamespace(idFromName=lambda name: calls.append(name) or "fixed",
        get=lambda identity: SimpleNamespace(runRecurring=tick) if identity == "fixed" else None)
    worker = entry.Default()
    worker.env = NoPreviewEnvironment(**ENABLED, RECURRING_SCHEDULER=namespace)
    asyncio.run(worker.scheduled(SimpleNamespace(cron=PRODUCTION_RECURRING_CRON, scheduledTime=(NOW+99999)*1000),
        NoEffects(), NoEffects()))
    assert calls == [RECURRING_SCHEDULER_SCOPE, "completed"]


@pytest.mark.parametrize("result", [{"ok": False}, {"ok": "true"}, {"ok": 1}, {}, SimpleNamespace(ok="false")])
def test_production_scheduled_unknown_rpc_result_not_retried_or_fallback(result):
    entry = load_entry()
    calls = []
    async def tick():
        calls.append(1)
        return result
    worker = entry.Default()
    worker.env = NoPreviewEnvironment(**ENABLED, RECURRING_SCHEDULER=SimpleNamespace(
        idFromName=lambda _: "fixed", get=lambda _: SimpleNamespace(runRecurring=tick)))
    with pytest.raises(RuntimeError, match="RECURRING_EXECUTION_UNAVAILABLE"):
        asyncio.run(worker.scheduled(SimpleNamespace(cron=PRODUCTION_RECURRING_CRON, scheduledTime=NOW*1000), None, None))
    assert calls == [1]


def test_production_missing_namespace_cannot_fall_back_to_preview():
    entry = load_entry()
    worker = entry.Default()
    worker.env = NoPreviewEnvironment(**ENABLED)
    with pytest.raises(RuntimeError, match="RECURRING_SCHEDULER_REQUIRED"):
        asyncio.run(worker.scheduled(SimpleNamespace(cron=PRODUCTION_RECURRING_CRON, scheduledTime=NOW*1000), None, None))


@pytest.mark.parametrize("cron", ["0 * * * *", "0 16 * * *", "10 * * * *", "0 0 * * *"])
def test_production_rejects_old_hourly_and_unreviewed_daily_triggers_without_rpc(cron):
    entry = load_entry()
    worker = entry.Default()
    worker.env = NoEffects(**ENABLED)
    assert PRODUCTION_RECURRING_CRON == "10 16 * * *"
    with pytest.raises(RuntimeError, match="RECURRING_TRIGGER_INVALID"):
        asyncio.run(worker.scheduled(SimpleNamespace(cron=cron, scheduledTime=NOW*1000), None, None))


def test_rpc_no_caller_clock_and_no_http_tick_reset_or_debug():
    entry = load_entry()
    scheduler = entry.RecurringScheduler(NoEffects(), NoEffects(**ENABLED))
    for kwargs in ({"now": NOW}, {"hour": NOW//3600}):
        with pytest.raises(TypeError):
            asyncio.run(scheduler.runRecurring(**kwargs))
    with pytest.raises(TypeError):
        asyncio.run(scheduler.runRecurring(NOW))
    assert asyncio.run(scheduler.fetch(NoEffects())).status == 405
    assert scheduler.journal is None


def test_idle_keeps_expired_unrelated_activity_and_never_writes_d1(production):
    p = production
    with p.app.store._immediate() as db:
        db.execute("""INSERT INTO ledger_activity_events(id,operation_id,owner_id,target_kind,
            actor_json,resource_kind,resource_id,action,created_at)
            VALUES('old-event','old-op','owner','shared','{}','expense','old-expense','create',
                '2020-01-01T00:00:00Z')""")
    first = asyncio.run(p.coordinator.runRecurring())
    assert first["ok"] is True and first["scanned"] == first["created"] == 0
    assert first["metrics"]["rowsWritten"] == 0 and first["metrics"]["complete"] is True
    assert p.raw.local_changes == 0
    assert len(p.app.rows("ledger_activity_events")) == 1
    assert all(sql.lstrip().upper().startswith("SELECT")
        for batch in p.raw.dispatched for sql, _ in batch)
    before = len(p.raw.dispatched)
    assert asyncio.run(p.coordinator.runRecurring())["skipped"] is True
    assert len(p.raw.dispatched) == before
    p.clock[0] += 3600
    assert asyncio.run(p.coordinator.runRecurring())["ok"] is True
    assert len(p.raw.dispatched) == before  # daily dedupe also spans later hours
    assert p.raw.local_changes == 0


@pytest.mark.parametrize("corruption", [
    "DROP TABLE expense_recurring_pending",
    "DROP TRIGGER expense_recurring_pending_insert_cap",
    "DELETE FROM d1_migrations WHERE name='0012_recurring_pending.sql'",
])
def test_missing_or_partial_schema_fails_closed_without_initialization_or_d1_write(production, corruption):
    p = production
    with p.app.store._immediate() as db:
        db.execute(corruption)
    result = asyncio.run(p.coordinator.runRecurring())
    assert result["ok"] is False and result["error"] == "RECURRING_SCHEMA_REQUIRED"
    assert p.raw.local_changes == 0
    count = len(p.raw.dispatched)
    restarted = p.entry.RecurringScheduler(p.ctx, p.env)
    assert asyncio.run(restarted.runRecurring())["error"] == "RECURRING_OUTCOME_UNKNOWN"
    assert len(p.raw.dispatched) == count


def test_generation_uses_current_free_owner_and_same_hour_dedup_persists_restart(production):
    p = production
    rule = create(p.app)
    legacy_due(p.app)
    with p.app.store._immediate() as db:
        name = record_name("users", "owner")
        user = json.loads(db.execute("SELECT payload FROM app_state WHERE name=?", (name,)).fetchone()[0])
        user["billing"] = {"plan": "free"}
        db.execute("UPDATE app_state SET payload=? WHERE name=?", (encode_record("users", "owner", user), name))
    result = asyncio.run(p.coordinator.runRecurring())
    assert result["ok"] is True and result["scanned"] == 1 and result["created"] == 3
    assert result["metrics"]["complete"] is True and result["metrics"]["rowsWritten"] > 0
    assert len(p.app.rows("expenses")) == len(p.app.rows("expense_events")) == 3
    assert len(p.app.rows("expense_recurring_occurrences")) == 3
    assert {row["actor_kind"] for row in p.app.rows("expense_events")} == {"schedule"}
    assert {row["actor_id"] for row in p.app.rows("expense_events")} == {rule["id"] + ":owner"}
    before = len(p.raw.dispatched)
    restarted = p.entry.RecurringScheduler(p.ctx, p.env)
    assert asyncio.run(restarted.runRecurring())["skipped"] is True
    assert len(p.raw.dispatched) == before


def test_owner_chunks_remove_global_ten_cap_but_keep_three_per_rule(production):
    p = production
    for index in range(12):
        status, _ = p.app.call("POST", body=draft(purpose=str(index)), key="local-rule-"+str(index))
        assert status == 201
    legacy_due(p.app)
    result = asyncio.run(p.coordinator.runRecurring())
    assert result["ok"] is True and result["scanned"] == 12 and result["created"] == 36
    occurrences = p.app.rows("expense_recurring_occurrences")
    assert len(occurrences) == 36
    assert max(sum(item["rule_id"] == row["rule_id"] for item in occurrences) for row in occurrences) <= 3


@pytest.mark.parametrize("withdraw", [
    "UPDATE workspace_members SET removed_at='removed' WHERE user_id='editor'",
    "UPDATE expense_categories SET archived_at='archived' WHERE id='cat_1'",
])
def test_current_actor_and_category_fences_apply_to_production_occurrences(production, withdraw):
    p = production
    status, _ = p.app.call("POST", body=draft(), actor="editor")
    assert status == 201
    legacy_due(p.app)
    with p.app.store._immediate() as db:
        db.execute(withdraw)
    result = asyncio.run(p.coordinator.runRecurring())
    assert result["ok"] is True and result["created"] == 0 and result["blocked"] == 1
    assert not p.app.rows("expenses") and not p.app.rows("expense_recurring_occurrences")


def test_current_owner_allowance_not_prior_creation_entitlement(production):
    p = production
    create(p.app)
    legacy_due(p.app)
    p.env.NORULO_PLAN_LIMITS_JSON = json.dumps({"pro": {"writesPerMonth": 1}})
    result = asyncio.run(p.coordinator.runRecurring())
    assert result["ok"] is True and result["created"] == 0 and result["blocked"] == 1
    assert p.app.rows("expense_recurring_rules")[0]["blocked_code"] == "MONTHLY_WRITE_LIMIT"
    assert not p.app.rows("expenses")


@pytest.mark.parametrize("failure", [RuntimeError("private native failure"), asyncio.TimeoutError()])
def test_unknown_native_outcome_stays_stopped_after_restart_and_never_retries(production, failure):
    p = production
    p.raw.failure = failure
    result = asyncio.run(p.coordinator.runRecurring())
    assert result["ok"] is False and result["metrics"]["complete"] is False
    count = len(p.raw.dispatched)
    p.raw.failure = None
    restarted = p.entry.RecurringScheduler(p.ctx, p.env)
    p.clock[0] += 3600
    assert asyncio.run(restarted.runRecurring())["error"] == "RECURRING_OUTCOME_UNKNOWN"
    assert len(p.raw.dispatched) == count


def test_committed_expense_with_lost_native_response_is_never_reissued(production):
    p = production
    create(p.app)
    legacy_due(p.app)
    def lose_financial_response():
        if any("INSERT INTO expenses(" in sql for sql, _ in p.raw.dispatched[-1]):
            raise RuntimeError("synthetic lost response after local atomic commit")
    p.raw.after_commit = lose_financial_response
    result = asyncio.run(p.coordinator.runRecurring())
    assert result["ok"] is True and result["failedOwners"] == 1 and result["metrics"]["complete"] is False
    assert len(p.app.rows("expenses")) == len(p.app.rows("expense_recurring_occurrences")) == 1
    assert len(p.app.rows("expense_events")) == 1
    before = len(p.raw.dispatched)
    p.raw.after_commit = None
    p.clock[0] += 3600
    restarted = p.entry.RecurringScheduler(p.ctx, p.env)
    assert asyncio.run(restarted.runRecurring())["skipped"] is True
    assert len(p.raw.dispatched) == before and len(p.app.rows("expenses")) == 1
    owner = p.owners[owner_scope("owner")]
    p.clock[0] += 86400
    assert asyncio.run(owner.runOwnerChunk("owner", daily_epoch(p.clock[0]), 0))["error"] == "RECURRING_OUTCOME_UNKNOWN"
    assert len(p.raw.dispatched) == before


@pytest.mark.parametrize("constraint", ["plan_record_limit", "plan_write_rate", "plan_monthly_write_limit"])
def test_unknown_native_constraint_not_swallowed_into_quota_maintenance(production, constraint):
    p = production
    create(p.app)
    legacy_due(p.app)
    before_rule = p.app.rows("expense_recurring_rules")[0]
    original = p.raw.batch
    failed_batches = []
    async def named_constraint(statements):
        statements = list(statements)
        if any("INSERT INTO expenses(" in item.sql for item in statements):
            failed_batches.append([item.sql for item in statements])
            raise RuntimeError("CHECK constraint failed: " + constraint)
        return await original(statements)
    p.monkeypatch.setattr(p.raw, "batch", named_constraint)
    result = asyncio.run(p.coordinator.runRecurring())
    assert result["ok"] is True and result["failedOwners"] == 1 and result["metrics"]["complete"] is False
    assert len(failed_batches) == 1
    owner = p.owners[owner_scope("owner")]
    assert asyncio.run(owner.ownerProgress("owner", daily_epoch(NOW)))["state"] == "stopped"
    assert not p.app.rows("expenses") and not p.app.rows("expense_recurring_pending")
    rule = p.app.rows("expense_recurring_rules")[0]
    assert rule["status"] == "active"
    assert all(rule[field] == before_rule[field] for field in ("next_period_key", "next_run_at", "revision"))
    # No post-failure maintenance advanced the pointer or swallowed the unknown.
    assert all(not any("UPDATE expense_recurring_rules SET" in sql for sql, _ in batch)
        for batch in p.raw.dispatched)


def test_missing_native_metadata_stops_even_if_sql_returned(production):
    p = production
    p.raw.metadata = False
    result = asyncio.run(p.coordinator.runRecurring())
    assert result["ok"] is False and result["metrics"]["complete"] is False
    assert p.coordinator.journal.snapshot()["state"] == "stopped"


@pytest.mark.parametrize("bad_metadata", [True, -1, 1.5, "0", None])
def test_malformed_native_metadata_never_counts_as_definite_outcome(production, bad_metadata):
    p = production
    original = p.raw.batch
    async def malformed(statements):
        results = await original(statements)
        results[0].meta.rows_written = bad_metadata
        return results
    p.monkeypatch.setattr(p.raw, "batch", malformed)
    result = asyncio.run(p.coordinator.runRecurring())
    assert result["ok"] is False and result["metrics"]["complete"] is False
    assert p.coordinator.journal.snapshot()["state"] == "stopped"


def test_cold_restart_inflight_marker_prevents_all_d1_contact(production):
    p = production
    journal = RecurringJournal(p.ctx.storage.sql)
    assert journal.begin(NOW//3600) is True
    assert asyncio.run(p.coordinator.runRecurring())["error"] == "RECURRING_OUTCOME_UNKNOWN"
    assert p.raw.dispatched == []


def test_owner_timeout_retains_durable_stop_without_retry(production):
    p = production
    p.monkeypatch.setattr(p.entry, "OWNER_SOFT_SECONDS", .02)
    async def run():
        p.raw.entered, p.raw.release = asyncio.Event(), asyncio.Event()
        owner = p.env.RECURRING_SCHEDULER.get(owner_scope("owner"))
        result = await owner.runOwnerChunk("owner", daily_epoch(NOW), 0)
        assert p.raw.entered.is_set()
        assert result["error"] == "RECURRING_OUTCOME_UNKNOWN" and result["metrics"]["complete"] is False
    asyncio.run(run())
    owner = p.owners[owner_scope("owner")]
    assert asyncio.run(owner.ownerProgress("owner", daily_epoch(NOW)))["state"] == "stopped"
    assert owner._waiting == 0 and not owner._lock.locked()


def test_rpc_cancellation_propagates_and_blocks_restarted_dispatch(production):
    p = production
    async def run():
        p.raw.entered, p.raw.release = asyncio.Event(), asyncio.Event()
        task = asyncio.create_task(p.coordinator.runRecurring())
        await p.raw.entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(run())
    assert p.coordinator.journal.snapshot()["state"] == "stopped"
    count = len(p.raw.dispatched)
    restarted = p.entry.RecurringScheduler(p.ctx, p.env)
    assert asyncio.run(restarted.runRecurring())["ok"] is False
    assert len(p.raw.dispatched) == count


def test_serial_queue_and_wait_are_bounded_without_storage_side_effects(production):
    p = production
    p.coordinator._waiting = 16
    assert asyncio.run(p.coordinator.runRecurring()) == {"ok": False, "error": "RECURRING_BUSY"}
    assert p.coordinator.journal is None and p.raw.dispatched == []
    p.coordinator._waiting = 0
    p.monkeypatch.setattr(p.entry, "RECURRING_QUEUE_WAIT_SECONDS", .01)
    async def run():
        async with p.coordinator._lock:
            result = await p.coordinator.runRecurring()
            assert result == {"ok": False, "error": "RECURRING_BUSY"}
    asyncio.run(run())
    assert p.coordinator._waiting == 0 and p.coordinator.journal is None


def test_two_local_rpc_tasks_serialize_and_complete_only_one_hour(production):
    p = production
    async def run():
        p.raw.entered, p.raw.release = asyncio.Event(), asyncio.Event()
        first = asyncio.create_task(p.coordinator.runRecurring())
        await p.raw.entered.wait()
        second = asyncio.create_task(p.coordinator.runRecurring())
        await asyncio.sleep(0)
        assert p.coordinator._waiting == 2
        p.raw.release.set()
        results = await asyncio.gather(first, second)
        assert all(item["ok"] is True for item in results)
        assert sum(item.get("skipped", False) for item in results) == 1
    asyncio.run(run())
    assert len(p.raw.dispatched) == 2  # schema batch, then one due SELECT
    assert p.coordinator._waiting == 0 and p.raw.local_changes == 0


def test_clock_rollback_cannot_write_or_dispatch_after_completed_hour(production):
    p = production
    assert asyncio.run(p.coordinator.runRecurring())["ok"] is True
    count = len(p.raw.dispatched)
    p.clock[0] -= 3600
    result = asyncio.run(p.coordinator.runRecurring())
    assert result["error"] == "RECURRING_CLOCK_INVALID"
    assert len(p.raw.dispatched) == count


def test_daily_cadence_keeps_existing_completed_utc_hour_state_without_migration(production):
    p = production
    # Model the already published hourly scheduler's completed state. A new
    # daily trigger must never reinterpret this persisted value as a UTC day.
    existing = RecurringJournal(p.ctx.storage.sql)
    previous_hour = NOW//3600-1
    assert existing.begin(previous_hour) is True
    existing.finish(previous_hour)
    assert asyncio.run(p.coordinator.runRecurring())["skipped"] is True
    assert p.coordinator.journal.snapshot()["completed_hour"] == previous_hour
    before = len(p.raw.dispatched)
    restarted = p.entry.RecurringScheduler(p.ctx, p.env)
    assert asyncio.run(restarted.runRecurring())["skipped"] is True
    assert len(p.raw.dispatched) == before
    p.clock[0] += 24*3600
    assert asyncio.run(restarted.runRecurring())["ok"] is True
    assert restarted.journal.snapshot()["completed_hour"] == NOW//3600+24
    assert p.raw.local_changes == 0  # no D1 heartbeat/migration/idle cleanup


@pytest.mark.parametrize("run_retention", [None, 1, "false"])
def test_housekeeping_mode_requires_exact_boolean_before_d1_access(run_retention):
    from norulo_server.cloudflare_ledger_recurring import run_due_recurring
    with pytest.raises(ValueError, match="recurring tick bounds"):
        asyncio.run(run_due_recurring(binding=NoEffects(), gateway=NoEffects(), now=NOW,
            run_retention=run_retention))

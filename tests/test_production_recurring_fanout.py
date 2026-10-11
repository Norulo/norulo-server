"""LOCAL protocol/SQLite proofs; no production D1 or provider calls."""
import asyncio
from types import SimpleNamespace

import pytest

import norulo_server.cloudflare_recurring_scheduler as scheduler
from test_ledger_recurring import app, create, legacy_due, draft, NOW
from test_production_recurring_scheduler import production, NoEffects
from norulo_server.cloudflare_state_records import record_name, encode_record
import json


class Discovery:
    def __init__(self, owners):
        self.owners, self.queries = sorted(owners), []
        self.reads = 0
    def prepare(self, sql):
        assert sql.startswith("SELECT DISTINCT owner_id")
        owner = self
        class Statement:
            def bind(self, cursor, epoch, limit):
                self.cursor, self.limit = cursor, limit
                return self
            async def all(self):
                rows = [value for value in owner.owners if value > self.cursor][:self.limit]
                owner.queries.append(self.cursor)
                owner.reads += len(rows)
                return SimpleNamespace(results=[{"owner_id": value} for value in rows])
        return Statement()
    def metrics(self):
        return {"operations": len(self.queries), "rowsRead": self.reads,
            "rowsWritten": 0, "complete": True}


def result(sequence, *, created=1, complete=True, deferred=False, retry=0, operations=1):
    return {"ok": True, "nextChunk": sequence + 1, "complete": complete,
        "deferred": deferred, "retryAt": retry, "scanned": 1,
        "created": created, "blocked": 0, "replayed": 0,
        "metrics": {"operations": operations, "rowsRead": 1, "rowsWritten": created * 3, "complete": True}}


def namespace(owners, run, progress=None):
    labels = {scheduler.owner_scope(owner): owner for owner in owners}
    def get(identity):
        owner = labels[identity]
        async def execute(supplied, epoch, sequence):
            assert supplied == owner
            return await run(owner, int(epoch), int(sequence))
        async def inspect(supplied, epoch):
            assert supplied == owner
            if progress is None:
                raise AssertionError("Unexpected progress lookup")
            return await progress(owner, int(epoch))
        return SimpleNamespace(runOwnerChunk=execute, ownerProgress=inspect)
    return SimpleNamespace(RECURRING_SCHEDULER=SimpleNamespace(idFromName=lambda name: name, get=get))


def test_eight_slow_minute_yields_do_not_hold_the_sixty_fifth_ready_owner(monkeypatch):
    owners = ["owner%03d" % index for index in range(65)]
    clock, calls, active, peak = [NOW], [], [0], [0]
    original_sleep = asyncio.sleep
    async def run(owner, epoch, sequence):
        calls.append((owner, sequence))
        active[0] += 1
        peak[0] = max(peak[0], active[0])
        await original_sleep(.001)
        active[0] -= 1
        if owner in owners[:8] and sequence == 0:
            return result(sequence, created=0, complete=False, deferred=True, retry=NOW+60)
        return result(sequence)
    async def advance(delay):
        assert all((owner, 0) in calls for owner in owners)
        assert delay == 60
        clock[0] += delay
        await original_sleep(0)
    monkeypatch.setattr(scheduler.asyncio, "sleep", advance)
    outcome = asyncio.run(scheduler.drain_owners(env=namespace(owners, run),
        observed=Discovery(owners), epoch=scheduler.daily_epoch(NOW), clock=lambda: clock[0]))
    assert outcome["created"] == outcome["selectedOwners"] == 65
    assert outcome["ownerRpcs"] == 73 and peak[0] == 8
    assert outcome["failedOwners"] == 0 and outcome["backlog"] is False
    assert outcome["checkpoint"] == {"cursor": "", "pending": []}


def test_unknown_chunks_keep_full_reservation_and_known_chunks_reclaim_unused(monkeypatch):
    owners = ["owner%03d" % index for index in range(3)]
    monkeypatch.setattr(scheduler, "MAX_DAILY_OCCURRENCES", 40)
    async def unknown(owner, epoch, sequence):
        await asyncio.sleep(0)
        return {"ok": False, "error": "RECURRING_OUTCOME_UNKNOWN",
            "metrics": {"operations": 2, "rowsRead": 3, "rowsWritten": 1, "complete": False}}
    outcome = asyncio.run(scheduler.drain_owners(env=namespace(owners, unknown),
        observed=Discovery(owners), epoch=scheduler.daily_epoch(NOW), clock=lambda: NOW))
    assert outcome["failedOwners"] == outcome["ownerRpcs"] == 2
    assert outcome["backlog"] is True and outcome["checkpoint"]["pending"] == [owners[2]]
    assert outcome["metrics"]["rowsWritten"] == 2 and outcome["metrics"]["complete"] is False
    async def known(owner, epoch, sequence):
        await asyncio.sleep(0)
        return result(sequence, created=5)
    known_outcome = asyncio.run(scheduler.drain_owners(env=namespace(owners, known),
        observed=Discovery(owners), epoch=scheduler.daily_epoch(NOW), clock=lambda: NOW))
    assert known_outcome["created"] == 15 and known_outcome["ownerRpcs"] == 3
    assert known_outcome["failedOwners"] == 0 and known_outcome["backlog"] is False


def test_unconfirmed_transport_waits_for_sibling_and_stops_root_before_new_launches():
    owners = ["owner%03d" % index for index in range(10)]
    finished, calls = [], []
    async def run(owner, epoch, sequence):
        calls.append(owner)
        if owner == owners[0]:
            await asyncio.sleep(0)
            raise RuntimeError("private transport diagnostic")
        await asyncio.sleep(.01)
        finished.append(owner)
        return result(sequence)
    async def progress(owner, epoch):
        return {"ok": True, "state": "active", "nextChunk": 0, "result": None}
    with pytest.raises(scheduler.RecurringFailure, match="RECURRING_OUTCOME_UNKNOWN") as raised:
        asyncio.run(scheduler.drain_owners(env=namespace(owners, run, progress),
            observed=Discovery(owners), epoch=scheduler.daily_epoch(NOW), clock=lambda: NOW))
    assert calls == owners[:8] and finished == owners[1:8]
    assert raised.value.counts["created"] == 7
    assert raised.value.metrics["rowsWritten"] == 21 and raised.value.metrics["complete"] is False


def test_lost_response_uses_one_readonly_settled_progress_without_replaying_chunk():
    owner, calls, lookups = "owner", [], []
    async def run(owner, epoch, sequence):
        calls.append(sequence)
        if sequence == 0:
            raise RuntimeError("response lost after settled DO progress")
        return result(sequence, created=2)
    async def progress(owner, epoch):
        lookups.append(owner)
        return {"ok": True, "state": "ready", "nextChunk": 1,
            "result": result(0, created=3, complete=False)}
    outcome = asyncio.run(scheduler.drain_owners(env=namespace([owner], run, progress),
        observed=Discovery([owner]), epoch=scheduler.daily_epoch(NOW), clock=lambda: NOW))
    assert calls == [0, 1] and lookups == [owner]
    assert outcome["created"] == 5 and outcome["ownerRpcs"] == 3
    assert outcome["metrics"]["rowsWritten"] == 15 and outcome["failedOwners"] == 0


def test_carry_owner_is_not_counted_again_after_keyset_wrap():
    owners = ["a_owner", "b_owner"]
    calls = []
    async def run(owner, epoch, sequence):
        calls.append(owner)
        return result(sequence, created=3)
    outcome = asyncio.run(scheduler.drain_owners(env=namespace(owners, run), observed=Discovery(owners),
        epoch=scheduler.daily_epoch(NOW), clock=lambda: NOW,
        previous={"cursor": "", "pending": [owners[0]]}))
    assert calls == owners and outcome["created"] == 6
    assert outcome["metrics"]["rowsWritten"] == 18 and outcome["failedOwners"] == 0


@pytest.mark.parametrize("method,args", [
    ("runRecurring", ()), ("runOwnerChunk", ("owner", scheduler.daily_epoch(NOW), 0)),
    ("ownerProgress", ("owner", scheduler.daily_epoch(NOW))),
])
def test_wrong_role_is_rejected_before_storage_or_d1(production, method, args):
    p = production
    wrong = p.entry.RecurringScheduler(SimpleNamespace(id="wrong", storage=NoEffects()), p.env)
    assert asyncio.run(getattr(wrong, method)(*args))["ok"] is False
    assert p.raw.dispatched == []


@pytest.mark.parametrize("owner,epoch,sequence", [
    ("bad owner", scheduler.daily_epoch(NOW), 0),
    ("owner", scheduler.daily_epoch(NOW)+86400, 0),
    ("owner", True, 0), ("owner", scheduler.daily_epoch(NOW), True),
    ("owner", scheduler.daily_epoch(NOW), -1),
])
def test_owner_rpc_input_rejected_before_storage(production, owner, epoch, sequence):
    p = production
    ctx = SimpleNamespace(id=scheduler.owner_scope("owner"), storage=NoEffects())
    worker = p.entry.RecurringScheduler(ctx, p.env)
    assert asyncio.run(worker.runOwnerChunk(owner, epoch, sequence))["ok"] is False
    assert p.raw.dispatched == []


def test_known_minute_quota_yields_without_blocking_or_advancing_failed_occurrence(production):
    p = production
    for index in range(3):
        assert p.app.call("POST", body=draft(purpose=str(index)), key=str(index))[0] == 201
    legacy_due(p.app)
    with p.app.store._immediate() as db:
        name = record_name("users", "owner")
        user = json.loads(db.execute("SELECT payload FROM app_state WHERE name=?", (name,)).fetchone()[0])
        user["billing"] = {"plan": "free"}
        db.execute("UPDATE app_state SET payload=? WHERE name=?", (encode_record("users", "owner", user), name))
    owner = p.env.RECURRING_SCHEDULER.get(scheduler.owner_scope("owner"))
    epoch = scheduler.daily_epoch(NOW)
    first = asyncio.run(owner.runOwnerChunk("owner", epoch, 0))
    assert first["deferred"] is True and first["complete"] is False
    assert first["created"] == 7 and first["retryAt"] == (NOW//60+1)*60
    assert all(row["status"] == "active" and row["blocked_code"] is None
        for row in p.app.rows("expense_recurring_rules"))
    before = len(p.raw.dispatched)
    duplicate = asyncio.run(owner.runOwnerChunk("owner", epoch, 0))
    assert duplicate == first and len(p.raw.dispatched) == before
    p.clock[0] = first["retryAt"]
    second = asyncio.run(owner.runOwnerChunk("owner", epoch, 1))
    assert second["complete"] is True and second["created"] == 2
    assert len(p.app.rows("expenses")) == 9
    assert max(sum(item["rule_id"] == row["rule_id"] for item in p.app.rows("expense_recurring_occurrences"))
        for row in p.app.rows("expense_recurring_occurrences")) == 3


def test_hard_native_sql_cap_never_dispatches_partial_batch(production):
    p = production
    observed = scheduler.ObservedRecurringD1(p.entry.NativeD1(p.raw), query_limit=2)
    asyncio.run(observed.batch([observed.prepare("SELECT 1")]))
    before = len(p.raw.dispatched)
    with pytest.raises(scheduler.RecurringFailure, match="RECURRING_SQL_LIMIT"):
        asyncio.run(observed.batch([observed.prepare("SELECT 2"), observed.prepare("SELECT 3")]))
    assert len(p.raw.dispatched) == before and observed.operations == 1 and observed.complete is True


def test_owner_journal_maximum_legal_snapshot_fits_single_bounded_row(production):
    p = production
    rules = ["r%03d" % index + "x"*116 for index in range(100)]
    state = {"owner": "o"*120, "epoch": scheduler.daily_epoch(NOW), "state": "ready", "nextChunk": 15,
        "rules": rules, "cursor": 100, "catchup": {rule: 3 for rule in rules}, "result": result(14)}
    scheduler.validate_owner_state(state, state["owner"])
    journal = scheduler.DispatchJournal(p.ctx.storage.sql, scheduler.owner_scope(state["owner"]))
    journal.write(state)
    assert journal.read() == state


@pytest.mark.parametrize("failure_site", ["checkpoint", "finish"])
def test_root_completion_storage_failure_preserves_known_financial_costs_and_stops(production, failure_site):
    p = production
    create(p.app)
    legacy_due(p.app)
    original = p.ctx.storage.sql.exec
    def broken(sql, *params):
        normalized = " ".join(sql.split())
        if (failure_site == "checkpoint" and normalized.startswith("INSERT INTO norulo_recurring_dispatch")
                or failure_site == "finish" and normalized.startswith("UPDATE norulo_recurring_scheduler SET state='idle'")):
            raise RuntimeError("private synthetic DO persistence failure")
        return original(sql, *params)
    p.monkeypatch.setattr(p.ctx.storage.sql, "exec", broken)
    outcome = asyncio.run(p.coordinator.runRecurring())
    assert outcome["ok"] is False and outcome["error"] == "RECURRING_OUTCOME_UNKNOWN"
    assert outcome["created"] == 3 and outcome["metrics"]["rowsWritten"] > 0
    assert outcome["metrics"]["complete"] is False
    assert len(p.app.rows("expenses")) == len(p.app.rows("expense_recurring_occurrences")) == 3
    assert p.coordinator.journal.snapshot()["state"] == "stopped"
    before = len(p.raw.dispatched)
    p.clock[0] += 86400
    restarted = p.entry.RecurringScheduler(p.ctx, p.env)
    assert asyncio.run(restarted.runRecurring())["error"] == "RECURRING_OUTCOME_UNKNOWN"
    assert len(p.raw.dispatched) == before


def test_unconfirmed_rpc_progress_stops_legacy_root_across_next_day(production):
    p = production
    create(p.app)
    legacy_due(p.app)
    calls = []
    async def lost(*args):
        calls.append("dispatch")
        raise RuntimeError("private lost RPC transport")
    async def active(*args):
        calls.append("progress")
        return {"ok": True, "state": "active", "nextChunk": 0}
    p.env.RECURRING_SCHEDULER.get = lambda identity: SimpleNamespace(runOwnerChunk=lost, ownerProgress=active)
    outcome = asyncio.run(p.coordinator.runRecurring())
    assert calls == ["dispatch", "progress"] and outcome["ok"] is False
    assert outcome["error"] == "RECURRING_OUTCOME_UNKNOWN" and outcome["metrics"]["complete"] is False
    assert p.coordinator.journal.snapshot()["state"] == "stopped"
    before = len(p.raw.dispatched)
    p.clock[0] += 86400
    restarted = p.entry.RecurringScheduler(p.ctx, p.env)
    assert asyncio.run(restarted.runRecurring())["error"] == "RECURRING_OUTCOME_UNKNOWN"
    assert len(p.raw.dispatched) == before and calls == ["dispatch", "progress"]

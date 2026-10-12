"""Account preference writes share the existing atomic commercial allowance."""
import asyncio
import json
import sqlite3

import pytest

from test_ledger_recurring import NOW, app
from norulo_server.cloudflare_ledger_api import handle_ledger_request
from norulo_server.cloudflare_plan_limits import PlanLimitedD1, PlanLimitError
from norulo_server.cloudflare_state_records import encode_record, record_name


PREFERENCES = (("jev", "enabled", True),
               ("expense-retention", "autoRemoveOldestExpense", False))


def request(app, resource, *, method="GET", enabled=None, field=None, revision=1,
            actor="owner", **headers):
    return asyncio.run(handle_ledger_request(
        binding=PlanLimitedD1(app.raw, policy=app.policy, now=NOW), gateway=None,
        method=method, path="/api/v1/account/" + resource, params={}, now=NOW,
        body=None if field is None else {field: enabled},
        headers={"Cookie": "nr_session=" + actor, "Origin": "https://app.example.test",
                 "If-Match": f'"{revision}"', **headers}))


def facts(app):
    return {table: app.rows(table) for table in (
        "app_state", "ledger_plan_usage", "expenses", "expense_events", "d1_command_guard")}


@pytest.mark.parametrize("resource,field,initial", PREFERENCES)
@pytest.mark.parametrize("quota,code", [
    ("writesPerMinute", "WRITE_RATE_LIMIT"), ("writesPerMonth", "MONTHLY_WRITE_LIMIT")])
def test_exact_last_preference_write_is_charged_and_next_denied_without_changes(
        app, resource, field, initial, quota, code):
    app.policy["pro"][quota] = 2
    before = facts(app)
    assert request(app, resource)[0] == 200
    assert facts(app) == before
    assert request(app, resource, method="PATCH", field=field, enabled=not initial)[0] == 200
    assert request(app, resource, method="PATCH", field=field, enabled=initial, revision=2)[0] == 200
    usage = app.rows("ledger_plan_usage")[0]
    assert (usage["owner_id"], usage["writes"], usage["minute_writes"], usage["projects"],
            usage["records"], usage["jev_reserved_microusd"]) == ("owner", 2, 2, 1, 0, 0)
    before = facts(app)
    assert request(app, resource, method="PATCH", field=field, enabled=not initial, revision=3) == (
        429, {"error": {"code": code}})
    assert facts(app) == before
    # A confirmed no-op and a stale precondition do not dispatch a mutation.
    assert request(app, resource, method="PATCH", field=field, enabled=initial, revision=3)[0] == 200
    assert request(app, resource, method="PATCH", field=field, enabled=not initial, revision=2)[0] == 412
    assert request(app, resource)[1]["revision"] == 3
    assert facts(app) == before


def test_preferences_share_allowance_with_ledger_and_charge_actual_account(app):
    app.policy["pro"]["writesPerMinute"] = 1
    assert request(app, "expense-retention", method="PATCH", field="autoRemoveOldestExpense",
                   enabled=True, actor="viewer", **{"X-Norulo-Workspace": "owner"})[0] == 200
    usage = app.rows("ledger_plan_usage")
    assert len(usage) == 1 and usage[0]["owner_id"] == "viewer" and usage[0]["writes"] == 1
    assert request(app, "jev", method="PATCH", field="enabled", enabled=False)[0] == 200
    before = facts(app)
    result = asyncio.run(handle_ledger_request(
        binding=PlanLimitedD1(app.raw, policy=app.policy, now=NOW), gateway=None,
        method="POST", path="/api/v1/categories", params={}, body={"name": "Another category"},
        headers={"Cookie": "nr_session=owner", "Origin": "https://app.example.test"}, now=NOW))
    assert result == (429, {"error": {"code": "WRITE_RATE_LIMIT"}})
    assert facts(app) == before


def test_quota_exhaustion_does_not_charge_auth_cleanup_or_read_batches(app):
    app.policy["pro"]["writesPerMinute"] = 1
    assert request(app, "jev", method="PATCH", field="enabled", enabled=False)[0] == 200
    before_usage = app.rows("ledger_plan_usage")
    limited = PlanLimitedD1(app.raw, policy=app.policy, now=NOW)
    session_name = record_name("sessions", "other")
    user_name = record_name("users", "other")
    user = next(row for row in app.rows("app_state") if row["name"] == user_name)
    updated = {**json.loads(user["payload"]), "name": "Refreshed identity"}
    asyncio.run(limited.batch([
        limited.prepare("DELETE FROM app_state WHERE name=?").bind(session_name),
        limited.prepare("UPDATE app_state SET payload=?,updated_at=? WHERE name=? AND payload=?").bind(
            encode_record("users", "other", updated), NOW, user_name, user["payload"]),
        limited.prepare("SELECT payload FROM app_state WHERE name=?").bind(user_name)]))
    assert app.rows("ledger_plan_usage") == before_usage
    assert not any(row["name"] == session_name for row in app.rows("app_state"))


def preference_commands(app, limited, *, fenced_id="owner"):
    name = record_name("users", "owner")
    previous = next(row for row in app.rows("app_state") if row["name"] == name)["payload"]
    updated = {**json.loads(previous), "jevEnabled": False, "jevPreferenceRevision": 2}
    return [limited.prepare("""INSERT INTO d1_command_guard(ok) VALUES(CASE WHEN
        EXISTS(SELECT 1 FROM app_state u WHERE u.name=? AND u.payload=?) THEN 1 ELSE 0 END)""").bind(
            record_name("users", fenced_id), previous),
        limited.prepare("UPDATE app_state SET payload=?,updated_at=? WHERE name=? AND payload=?").bind(
            encode_record("users", "owner", updated), NOW, name, previous),
        limited.prepare("INSERT INTO d1_command_guard(ok) VALUES(CASE WHEN changes()=1 THEN 1 ELSE 0 END)"),
        limited.prepare("DELETE FROM d1_command_guard")]


def test_preference_mutation_requires_exact_owner_fence_and_cannot_hide_in_model_reservation(app):
    limited = PlanLimitedD1(app.raw, policy=app.policy, now=NOW)
    before, batches = facts(app), app.raw.batch_count
    with pytest.raises(PlanLimitError, match="USAGE_GUARD_UNAVAILABLE"):
        asyncio.run(limited.batch(preference_commands(app, limited, fenced_id="other")))
    with pytest.raises(PlanLimitError, match="USAGE_GUARD_UNAVAILABLE"):
        asyncio.run(limited.reserve_jev(preference_commands(app, limited)))
    with pytest.raises(PlanLimitError, match="USAGE_GUARD_UNAVAILABLE"):
        asyncio.run(preference_commands(app, limited)[1].first())
    assert facts(app) == before and app.raw.batch_count == batches


def test_failed_preference_batch_rolls_back_usage_and_guard_rows(app):
    limited = PlanLimitedD1(app.raw, policy=app.policy, now=NOW)
    commands = preference_commands(app, limited)
    commands.insert(-1, limited.prepare("INSERT INTO d1_command_guard(ok) VALUES(0)"))
    before = facts(app)
    with pytest.raises(sqlite3.IntegrityError):
        asyncio.run(limited.batch(commands))
    assert facts(app) == before


def test_concurrent_ledger_write_at_last_slot_atomically_rolls_back_preference(app):
    app.policy["pro"]["writesPerMinute"] = 2
    assert request(app, "expense-retention", method="PATCH",
                   field="autoRemoveOldestExpense", enabled=True)[0] == 200
    limited = PlanLimitedD1(app.raw, policy=app.policy, now=NOW)
    commands, before_users = preference_commands(app, limited), app.rows("app_state")

    def use_last_slot_after_preflight():
        app.raw.before_batch = None
        result = asyncio.run(handle_ledger_request(
            binding=PlanLimitedD1(app.raw, policy=app.policy, now=NOW), gateway=None,
            method="POST", path="/api/v1/categories", params={}, body={"name": "Concurrent category"},
            headers={"Cookie": "nr_session=owner", "Origin": "https://app.example.test"}, now=NOW))
        assert result[0] == 201

    # The test adapter invokes this after quota preflight, before the transaction.
    # Run the other coroutine in a thread because the preference event loop is active.
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=1) as executor:
        app.raw.before_batch = lambda: executor.submit(use_last_slot_after_preflight).result()
        with pytest.raises(PlanLimitError, match="WRITE_RATE_LIMIT"):
            asyncio.run(limited.batch(commands))
    assert app.rows("app_state") == before_users
    assert app.rows("ledger_plan_usage")[0]["writes"] == 2
    assert app.rows("ledger_plan_usage")[0]["minute_writes"] == 2
    assert any(row["name"] == "Concurrent category" for row in app.rows("expense_categories"))
    assert app.rows("d1_command_guard") == []

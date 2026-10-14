"""Production ingress with local paid fixtures and a simulated Jev boundary.

These tests exercise canonical auth/CAS/quota SQL on tmp_path SQLite. They do
not establish an actual account's paid entitlement, native Workers FFI, provider
quality, billing acceptance, or remote D1 behavior. No real secret/provider is
used; the production gateway's activation logic remains intact.
"""
import json

import pytest

from norulo_server.cloudflare_state_records import encode_record, record_name
from norulo_server.ledger_plan_policy import JEV_RESERVATION_MICROUSD
from test_cloudflare_github_identity_http import D1ShapedSQLite
from test_ledger_automatic_assistance import Provider
from test_worker_production_runtime import NOW, ORIGIN, TOKEN, call, cookie, runtime


def _user(runtime, owner="owner", *, plan="pro", enabled=True, **billing):
    """Set a synthetic local billing snapshot, never a remote paid grant."""
    with runtime.store.connect() as db:
        name = record_name("users", owner)
        user = json.loads(db.execute("SELECT payload FROM app_state WHERE name=?", (name,)).fetchone()[0])
        user.update(jevEnabled=enabled, jevPreferenceRevision=1)
        user["billing"] = {"plan": plan, "status": "active",
                           "currentPeriodStart": NOW - 60, "currentPeriodEnd": NOW + 3600,
                           **billing}
        db.execute("UPDATE app_state SET payload=? WHERE name=?",
                   (encode_record("users", owner, user), name))


@pytest.fixture
def jev(runtime, monkeypatch):
    runtime.worker.env.NORULO_JEV_SUGGESTIONS_ENABLED = "1"
    runtime.worker.env.NORULO_JEV_SUGGESTIONS_EVALUATED = "1"
    runtime.worker.env.TYPESAFE_API_KEY = "local-simulated-provider-key"
    _user(runtime)
    provider = Provider()

    async def evaluate(gateway, request):
        assert gateway.enabled is True
        return await provider.evaluate(request)

    monkeypatch.setattr(runtime.entry.WorkerJevGateway, "evaluate", evaluate)
    runtime.provider = provider
    return runtime


def _draft(category=None):
    return {"target": {"kind": "shared"}, "occurredOn": "2026-09-27",
            "amount": "12.50", "currency": "USD", "purpose": "Local hosting bill",
            **({"categoryId": category} if category else {})}


def _write(runtime, *, key="one", category=None, headers=None):
    headers = headers if headers is not None else cookie(origin=ORIGIN)
    return call(runtime, "/api/v1/expenses", method="POST", body=_draft(category),
                headers={**headers, "idempotency-key": key})


def _suggest(runtime, headers=None):
    return call(runtime, "/api/v1/expense-suggestions", method="POST", body=_draft(),
                headers=headers if headers is not None else cookie(origin=ORIGIN))


def _usage(runtime, owner="owner"):
    with runtime.store.connect() as db:
        row = db.execute("SELECT * FROM ledger_plan_usage WHERE owner_id=?", (owner,)).fetchone()
        return dict(row) if row else None


def _counts(runtime):
    with runtime.store.connect() as db:
        return {table: db.execute(f"SELECT COUNT(*) FROM {table} WHERE owner_id='owner'").fetchone()[0]
                for table in ("expenses", "expense_events", "expense_suggestion_events")}


def _member(runtime, *, plan="free", enabled=True):
    _user(runtime, "other", plan=plan, enabled=enabled)
    with runtime.store.connect() as db:
        session = {"userId": "other", "expiresAt": NOW + 3600}
        db.execute("INSERT INTO app_state(name,payload,updated_at) VALUES(?,?,?)",
                   (record_name("sessions", "member-session"),
                    encode_record("sessions", "member-session", session), NOW))
        db.execute("""INSERT INTO workspace_members(workspace_id,user_id,role,revision,
            joined_at,updated_at,removed_at,invited_by_user_id)
            VALUES('owner','other','editor',1,'local','local',NULL,'owner')""")
    return {"cookie": "nr_session=member-session", "origin": ORIGIN,
            "x-norulo-workspace": "owner"}


@pytest.mark.parametrize("plan,budget", [("pro", "3.00"), ("max", "12.00")])
def test_enabled_paid_production_owner_and_key_share_one_allowance_without_replay(jev, plan, budget):
    _user(jev, plan=plan)
    profile = call(jev, "/api/v1/me", headers=cookie())
    assert profile.status == 200
    assert profile.payload["entitlements"]["jev"] == {
        "eligible": True, "enabled": True, "available": True,
        "monthlyBudgetUsd": budget, "period": "utc-calendar-month", "rollover": False}
    assert _usage(jev) is None and jev.provider.calls == []

    first = _write(jev)
    assert first.status == 201 and first.payload["categoryId"] == "cat_owner"
    assert first.payload["assistance"]["categorySource"] == "jev"
    assert first.payload["amount"] == "12.50" and first.payload["target"] == {"kind": "shared"}
    before = _usage(jev)
    replay = _write(jev)
    assert replay.status == 201 and replay.payload == first.payload
    assert _usage(jev) == before and len(jev.provider.calls) == 1

    second = _write(jev, key="key-write", category="cat_owner",
                    headers={"authorization": "Bearer " + TOKEN})
    assert second.status == 201 and second.payload["assistance"]["categorySource"] == "user"
    assert len(jev.provider.calls) == 2
    usage = _usage(jev)
    assert (usage["records"], usage["writes"], usage["jev_reserved_microusd"]) == (
        2, 2, 2 * JEV_RESERVATION_MICROUSD)
    assert _usage(jev, "other") is None
    with jev.store.connect() as db:
        assert {row[0] for row in db.execute("SELECT actor_kind FROM expense_events WHERE owner_id='owner'")} == {
            "session", "api_key"}
        assert db.execute("SELECT COUNT(*) FROM d1_command_guard").fetchone()[0] == 0


@pytest.mark.parametrize("owner_plan", ["pro", "max"])
def test_free_member_uses_owner_activation_and_shares_owner_allowance(jev, owner_plan):
    _user(jev, plan=owner_plan)
    headers = _member(jev, plan="free", enabled=False)
    profile = call(jev, "/api/v1/me", headers=headers)
    assert profile.status == 200 and profile.payload["id"] == "other"
    assert profile.payload["entitlements"]["plan"] == owner_plan
    assert profile.payload["entitlements"]["jev"]["available"] is True
    assert _write(jev, headers=headers, key="member").status == 201
    assert _write(jev, key="owner").status == 201
    assert len(jev.provider.calls) == 2
    assert _usage(jev)["jev_reserved_microusd"] == 2 * JEV_RESERVATION_MICROUSD
    assert _usage(jev, "other") is None


@pytest.mark.parametrize("owner_plan,enabled", [("free", True), ("pro", False)])
def test_paid_member_cannot_override_owner_entitlement_or_preference(jev, owner_plan, enabled):
    _user(jev, plan=owner_plan, enabled=enabled)
    headers = _member(jev, plan="max", enabled=True)
    profile = call(jev, "/api/v1/me", headers=headers)
    assert profile.payload["entitlements"]["jev"]["available"] is False
    automatic = _write(jev, headers=headers)
    assert automatic.status == 422 and automatic.payload["error"]["code"] == "CATEGORY_REQUIRED"
    assert _write(jev, headers=headers, key="manual", category="cat_owner").status == 201
    assert jev.provider.calls == [] and _usage(jev)["jev_reserved_microusd"] == 0


@pytest.mark.parametrize("disabled", ["enabled", "evaluated", "secret", "preference", "expired", "future", "canceled"])
def test_production_admission_requires_all_activation_and_current_paid_entitlement(jev, disabled):
    if disabled in {"enabled", "evaluated"}:
        setattr(jev.worker.env, "NORULO_JEV_SUGGESTIONS_" + disabled.upper(), "0")
    elif disabled == "secret":
        jev.worker.env.TYPESAFE_API_KEY = " \n"
    elif disabled == "preference":
        _user(jev, enabled=False)
    elif disabled == "expired":
        _user(jev, currentPeriodEnd=NOW)
    elif disabled == "future":
        _user(jev, currentPeriodStart=NOW + 1)
    else:
        _user(jev, status="canceled")
    profile = call(jev, "/api/v1/me", headers=cookie())
    assert profile.payload["entitlements"]["jev"]["available"] is False
    automatic = _write(jev)
    assert automatic.status == 422 and automatic.payload["error"]["code"] == "CATEGORY_REQUIRED"
    assert _write(jev, key="manual", category="cat_owner").status == 201
    assert jev.provider.calls == [] and _usage(jev)["jev_reserved_microusd"] == 0


@pytest.mark.parametrize("origin", [None, "https://hostile.example.test"])
def test_untrusted_production_cookie_write_cannot_dispatch_or_reserve(jev, origin):
    headers = cookie(**({"origin": origin} if origin else {}))
    response = _write(jev, headers=headers)
    assert response.status == 403 and response.payload == {"error": {"code": "UNTRUSTED_ORIGIN"}}
    assert jev.provider.calls == [] and _usage(jev) is None
    assert _counts(jev) == {"expenses": 0, "expense_events": 0, "expense_suggestion_events": 0}


@pytest.mark.parametrize("restricted,code", [
    ("scope", "INSUFFICIENT_SCOPE"), ("target", "TARGET_FORBIDDEN"),
    ("workspace", "WORKSPACE_FORBIDDEN")])
def test_production_key_limits_are_enforced_before_ai_dispatch(jev, restricted, code):
    headers = {"authorization": "Bearer " + TOKEN}
    with jev.store.connect() as db:
        if restricted == "scope":
            db.execute("UPDATE api_keys SET scopes='[\"expenses:read\"]' WHERE id='key'")
        elif restricted == "target":
            db.execute("UPDATE api_keys SET restrictions='{\"shared\":false,\"projectIds\":[]}' WHERE id='key'")
        else:
            headers["x-norulo-workspace"] = "other"
    response = _write(jev, headers=headers)
    assert response.status == 403 and response.payload == {"error": {"code": code}}
    assert jev.provider.calls == [] and _usage(jev) is None


@pytest.mark.parametrize("plan", ["pro", "max"])
def test_production_monthly_exhaustion_denies_ai_but_preserves_manual_write(jev, plan):
    _user(jev, plan=plan)
    jev.worker.env.NORULO_PLAN_LIMITS_JSON = json.dumps({plan: {"jevMonthlyBudgetUsd": "0.002753"}})
    assert _write(jev).status == 201
    manual = _write(jev, key="manual", category="cat_owner")
    assert manual.status == 201 and manual.payload["categoryId"] == "cat_owner"
    assert manual.payload["assistance"]["reason"] == "JEV_BUDGET_LIMIT"
    automatic = _write(jev, key="automatic-after-cap")
    assert automatic.status == 422 and automatic.payload["error"]["code"] == "CATEGORY_REQUIRED"
    assert automatic.payload["assistance"]["reason"] == "JEV_BUDGET_LIMIT"
    suggestion = _suggest(jev)
    assert suggestion.status == 429 and suggestion.payload == {"error": {"code": "JEV_BUDGET_LIMIT"}}
    assert len(jev.provider.calls) == 1
    usage = _usage(jev)
    assert (usage["records"], usage["writes"], usage["jev_reserved_microusd"]) == (
        2, 2, JEV_RESERVATION_MICROUSD)


@pytest.mark.parametrize("failure", [TimeoutError("private-timeout-detail"), OSError("private-unknown-outcome-detail")])
def test_provider_failure_or_unknown_outcome_keeps_each_reservation_without_retry(jev, failure):
    jev.provider.failure = failure
    manual = _write(jev, category="cat_owner")
    assert manual.status == 201 and manual.payload["categoryId"] == "cat_owner"
    assert manual.payload["assistance"]["status"] == "unavailable"
    assert len(jev.provider.calls) == 1 and _usage(jev)["jev_reserved_microusd"] == JEV_RESERVATION_MICROUSD
    replay = _write(jev, category="cat_owner")
    assert replay.payload == manual.payload and len(jev.provider.calls) == 1
    automatic = _write(jev, key="automatic")
    assert automatic.status == 422 and automatic.payload["error"]["code"] == "CATEGORY_REQUIRED"
    assert len(jev.provider.calls) == 2
    assert _usage(jev)["jev_reserved_microusd"] == 2 * JEV_RESERVATION_MICROUSD
    assert _counts(jev) == {"expenses": 1, "expense_events": 1, "expense_suggestion_events": 2}
    assert "private-" not in json.dumps([manual.payload, automatic.payload])


@pytest.mark.parametrize("change,code", [("key", "UNAUTHENTICATED"), ("owner", "AUTHORIZATION_CHANGED")])
def test_production_authority_is_rechecked_after_inference_without_refund(jev, change, code):
    def changed_authority():
        if change == "owner":
            _user(jev, enabled=False)
        else:
            with jev.store.connect() as db:
                db.execute("UPDATE api_keys SET revoked_at=? WHERE id='key'", (NOW,))
    jev.provider.on_call = changed_authority
    response = _write(jev, headers={"authorization": "Bearer " + TOKEN})
    assert response.status == (401 if change == "key" else 403)
    assert response.payload == {"error": {"code": code}}
    assert len(jev.provider.calls) == 1
    assert _usage(jev)["jev_reserved_microusd"] == JEV_RESERVATION_MICROUSD
    assert _counts(jev) == {"expenses": 0, "expense_events": 0, "expense_suggestion_events": 0}


@pytest.mark.parametrize("committed", [False, True])
def test_uncertain_d1_reservation_never_dispatches_or_retries_and_keeps_committed_usage(jev, committed):
    class UncertainReservation(D1ShapedSQLite):
        reservation_batches = 0

        async def batch(self, statements):
            statements = list(statements)
            is_reservation = any(item.sql.lstrip().startswith("INSERT INTO ledger_plan_usage") for item in statements)
            if is_reservation:
                self.reservation_batches += 1
                if not committed:
                    raise OSError("private-local-storage-failure")
            result = await super().batch(statements)
            if is_reservation:
                raise OSError("private-local-commit-response-lost")
            return result

    binding = UncertainReservation(jev.store)
    jev.worker.env.DB = binding
    response = _suggest(jev)
    assert response.status == 409 and response.payload == {"error": {"code": "AUTHORIZATION_CHANGED"}}
    assert binding.reservation_batches == 1 and jev.provider.calls == []
    usage = _usage(jev)
    if committed:
        assert usage["jev_reserved_microusd"] == JEV_RESERVATION_MICROUSD
    else:
        assert usage is None
    assert _counts(jev) == {"expenses": 0, "expense_events": 0, "expense_suggestion_events": 0}
    profile = call(jev, "/api/v1/me", headers=cookie())
    assert profile.status == 200 and binding.reservation_batches == 1
    assert _usage(jev) == usage
    with jev.store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM d1_command_guard").fetchone()[0] == 0


def test_owner_snapshot_change_before_reservation_rolls_back_the_actual_cas_batch(jev):
    class ChangedOwner(D1ShapedSQLite):
        reservation_batches = 0

        async def batch(self, statements):
            statements = list(statements)
            if any(item.sql.lstrip().startswith("INSERT INTO ledger_plan_usage") for item in statements):
                self.reservation_batches += 1
                _user(jev, enabled=False)
            return await super().batch(statements)

    binding = ChangedOwner(jev.store)
    jev.worker.env.DB = binding
    response = _suggest(jev)
    assert response.status == 409 and response.payload == {"error": {"code": "AUTHORIZATION_CHANGED"}}
    assert binding.reservation_batches == 1 and jev.provider.calls == []
    assert _usage(jev) is None
    assert _counts(jev) == {"expenses": 0, "expense_events": 0, "expense_suggestion_events": 0}
    with jev.store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM d1_command_guard").fetchone()[0] == 0

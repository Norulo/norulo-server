"""Unconfigured payments leave Free usable without stale prices or billing writes."""
import asyncio
import json

import pytest

from ledger_d1_fixture import D1ShapedSQLite, seed, seed_auth
from norulo_server.cloudflare_billing_catalog import read_public_plan
from norulo_server.cloudflare_billing_catalog_refresh import read_or_refresh_catalog
from norulo_server.cloudflare_http_contract import handle_http_request
from norulo_server.cloudflare_plan_limits import PlanLimitedD1
from norulo_server.ledger_plan_policy import default_policy
from norulo_server import account_cycle_rules
from test_cloudflare_billing_mutations import CreemStub
from test_creem_catalog_projection import product
from test_ledger_plan_limits import write
from test_worker_production_runtime import NOW, TOKEN, call, cookie, runtime


def no_provider(*args, **kwargs):
    raise AssertionError("Disabled/invalid billing must not construct a provider")


def trace_sql(store, monkeypatch):
    statements = []
    original = store.connect

    def connect():
        connection = original()
        connection.set_trace_callback(statements.append)
        return connection

    monkeypatch.setattr(store, "connect", connect)
    return statements


def assert_read_only_without_catalog(statements):
    assert not any("billing_public_catalog" in sql.lower() for sql in statements)
    assert not any(sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "REPLACE"))
                   for sql in statements)


def old_paid_catalog(store, *, expires_at):
    from norulo_server.creem_public_catalog_rules import verified_public_catalog
    saved = verified_public_catalog({"pro": {"month": "prod-old"}, "max": {}},
        {"prod-old": product("prod-old", 9900, "every-month")})
    with store.connect() as db:
        db.execute("INSERT INTO billing_public_catalog VALUES(1,?,?,1,?)",
            (json.dumps(saved), expires_at, NOW))


@pytest.mark.parametrize("products", [None, "", "{}", '{"pro":{},"max":{}}'])
@pytest.mark.parametrize("catalog_expiry", [None, NOW - 1, NOW + 3600])
def test_production_free_catalog_ignores_absent_expired_and_fresh_paid_cache(
        runtime, monkeypatch, products, catalog_expiry):
    if products is not None:
        runtime.worker.env.NORULO_CREEM_PRODUCT_IDS_JSON = products
    # An old or partially removed credential cannot turn an empty product list
    # into provider activity or make historical prices purchasable.
    runtime.worker.env.NORULO_CREEM_API_KEY = "synthetic-unused"
    if catalog_expiry is not None:
        old_paid_catalog(runtime.store, expires_at=catalog_expiry)
    monkeypatch.setattr(runtime.entry, "WorkerCreemGateway", no_provider)
    statements = trace_sql(runtime.store, monkeypatch)
    response = call(runtime, "/billing/plan")
    assert response.status == 200
    payload = response.payload
    assert payload["provider"] == "disabled" and payload["enabled"] is False
    assert payload["page"]["checkoutAction"] is None
    assert "account" not in payload and "ledgerUsage" not in payload
    free, pro, maximum = payload["plans"]
    assert free["prices"]["month"] == {
        "amount": "0", "currency": "USD", "interval": "month", "configured": True}
    assert free["entitlements"]["limits"] == {
        "projects": 3, "expenseRecords": 300, "writesPerMinute": 10, "writesPerMonth": 1000}
    assert free["entitlements"]["jev"]["monthlyBudgetUsd"] == "0.00"
    assert free["entitlements"]["jev"]["eligible"] is True
    assert free["entitlements"]["jev"]["trialCalls"] == 20
    for plan in (pro, maximum):
        for interval in ("month", "year"):
            assert plan["prices"][interval] == {
                "amount": None, "currency": "USD", "interval": interval,
                "configured": False, "productId": None, "billingPeriod": None}
    assert statements == []
    assert response.headers["Cache-Control"] == "no-store"


INVALID_PRODUCTS = [
    "{", "null", "[]", "true",
    '{"pro":{"month":"prod-valid"}}',
    '{"pro":{},"max":{},"other":{}}',
    '{"pro":{"week":"prod-valid"},"max":{}}',
    '{"pro":{"month":"bad id"},"max":{}}',
    '{"pro":{"month":"prod-same"},"max":{"year":"prod-same"}}',
    '{"pro":{},"pro":{"month":"prod-valid"},"max":{}}',
    '{"pro":{"month":"prod-one","month":"prod-two"},"max":{}}',
    '{"pro":{"month":"prod-\\ud800"},"max":{}}',
]


@pytest.mark.parametrize("products", INVALID_PRODUCTS)
def test_invalid_configuration_is_not_free_fallback_or_old_cached_paid_catalog(
        runtime, monkeypatch, products):
    runtime.worker.env.NORULO_CREEM_PRODUCT_IDS_JSON = products
    old_paid_catalog(runtime.store, expires_at=NOW + 3600)
    monkeypatch.setattr(runtime.entry, "WorkerCreemGateway", no_provider)
    statements = trace_sql(runtime.store, monkeypatch)
    response = call(runtime, "/billing/plan")
    assert response.status == 503
    assert response.payload["error"]["code"] == "BILLING_CATALOG_UNAVAILABLE"
    assert "plans" not in response.payload
    assert statements == []


def test_disabled_catalog_uses_configured_policy_and_real_personal_usage(runtime, monkeypatch):
    runtime.worker.env.NORULO_CREEM_PRODUCT_IDS_JSON = "{}"
    runtime.worker.env.NORULO_PLAN_LIMITS_JSON = '{"free":{"projects":7,"records":19}}'
    monkeypatch.setattr(runtime.entry, "WorkerCreemGateway", no_provider)
    statements = trace_sql(runtime.store, monkeypatch)
    response = call(runtime, "/billing/plan", headers=cookie(**{"x-norulo-workspace": "other"}))
    assert response.status == 200
    assert response.payload["account"]["plan"] == "free"
    assert response.payload["ledgerUsage"]["workspaceId"] == "owner"
    assert response.payload["ledgerUsage"]["projects"]["limit"] == 7
    assert response.payload["ledgerUsage"]["expenseRecords"]["limit"] == 19
    assert response.payload["ledgerUsage"]["expenseRecords"]["used"] == 0
    assert response.payload["plans"][0]["entitlements"]["limits"]["projects"] == 7
    assert response.payload["plans"][0]["entitlements"]["limits"]["expenseRecords"] == 19
    assert_read_only_without_catalog(statements)


@pytest.mark.parametrize("headers", [
    {"authorization": "Bearer " + TOKEN},
    {"cookie": "nr_session=own-session", "authorization": "Basic invalid"},
    {"cookie": "nr_session=own-session", "x-norulo-api-key": TOKEN},
    {"cookie": "nr_session=expired"},
])
def test_disabled_public_catalog_does_not_disclose_cookie_account_to_keys_or_invalid_auth(
        runtime, monkeypatch, headers):
    monkeypatch.setattr(runtime.entry, "WorkerCreemGateway", no_provider)
    statements = trace_sql(runtime.store, monkeypatch)
    response = call(runtime, "/billing/plan", headers=headers)
    assert response.status == 200
    assert "account" not in response.payload and "ledgerUsage" not in response.payload
    assert_read_only_without_catalog(statements)


@pytest.mark.parametrize("mutation", ["revoke", "change_user"])
def test_disabled_catalog_drops_personal_data_if_auth_snapshot_changes(tmp_path, mutation):
    fixture, _, _ = seed(tmp_path / "billing.db")
    seed_auth(fixture)
    binding = D1ShapedSQLite(fixture.store)

    def change_before_snapshot():
        with fixture.store._immediate() as db:
            if mutation == "revoke":
                db.execute("DELETE FROM app_state WHERE name='record:sessions:session-local'")
            else:
                db.execute("UPDATE app_state SET payload=json_set(payload,'$.name','changed') "
                    "WHERE name='record:users:owner'")

    binding.before_batch = change_before_snapshot
    status, payload = asyncio.run(read_public_plan(binding=binding,
        headers={"Cookie": "nr_session=session-local"}, now=fixture.now, payments_disabled=True))
    assert status == 200 and payload["enabled"] is False
    assert "account" not in payload and "ledgerUsage" not in payload
    assert binding.batch_count == 1


def test_disabled_payments_preserve_paid_account_facts_and_exact_reserved_usage(tmp_path):
    fixture, _, frozen = seed(tmp_path / "paid-account.db")
    seed_auth(fixture)
    policy = default_policy()
    policy["pro"]["jevMonthlyBudgetUsd"] = "3.250001"
    raw = D1ShapedSQLite(fixture.store)
    binding = PlanLimitedD1(raw, policy=policy, now=fixture.now)
    write(binding, frozen, fixture, 1, kind="jev")
    with fixture.store._immediate() as db:
        db.execute("UPDATE ledger_plan_usage SET jev_reserved_microusd=1234567,jev_delta=0")
    raw.batch_count = 0
    with fixture.store.connect() as db:
        before = list(db.iterdump())
    status, payload = asyncio.run(read_public_plan(binding=binding,
        headers={"Cookie": "nr_session=session-local"}, now=fixture.now, payments_disabled=True))
    assert status == 200
    assert payload["account"]["plan"] == "pro"
    assert payload["account"]["subscriptionId"] == "sub_fixture"
    assert payload["ledgerUsage"]["jev"]["usedMicrousd"] == 1234567
    assert payload["ledgerUsage"]["jev"]["limitMicrousd"] == 3250001
    assert raw.batch_count == 1
    with fixture.store.connect() as db:
        assert list(db.iterdump()) == before


def test_catalog_account_grant_uses_the_authorization_timestamp(tmp_path, monkeypatch):
    fixture, _, _ = seed(tmp_path / "clock.db")
    seed_auth(fixture)
    from test_preview_plan_grants import grant
    with fixture.store._immediate() as db:
        user = json.loads(db.execute("SELECT payload FROM app_state "
            "WHERE name='record:users:owner'").fetchone()[0])
        user["billing"] = {"plan": "free"}
        user["previewPlanGrant"] = grant(fixture.now)
        db.execute("UPDATE app_state SET payload=? WHERE name='record:users:owner'",
            (json.dumps(user),))
    # Wall clock before the grant must not override the admitted snapshot time.
    monkeypatch.setattr(account_cycle_rules.time, "time", lambda: fixture.now - 100)
    status, payload = asyncio.run(read_public_plan(binding=D1ShapedSQLite(fixture.store),
        headers={"Cookie": "nr_session=session-local"}, now=fixture.now, payments_disabled=True))
    assert status == 200
    assert payload["account"]["plan"] == "max"
    assert payload["account"]["provider"] == "preview_grant"
    assert payload["account"]["previewPlanGrant"]["active"] is True


@pytest.mark.parametrize("products", [None, {"pro": {}}, {"pro": {}, "max": {}, "other": {}},
    {"pro": {"month": "same-id"}, "max": {"year": "same-id"}}])
def test_refresh_rejects_invalid_shapes_before_database_or_provider(products):
    class NoSideEffects:
        def __getattr__(self, name):
            raise AssertionError("Invalid payment configuration touched " + name)

    status, payload = asyncio.run(read_or_refresh_catalog(binding=NoSideEffects(),
        gateway=NoSideEffects(), headers={}, products=products, now=NOW))
    assert status == 503 and payload["error"]["diagnostic"] == "PRODUCT_BINDINGS_INVALID"


@pytest.mark.parametrize("path", ["/billing/checkout-sessions", "/billing/change-interval",
    "/billing/cancel-subscription", "/billing/resume-subscription"])
def test_invalid_product_config_fails_billing_mutations_before_provider_construction(
        runtime, monkeypatch, path):
    runtime.worker.env.NORULO_CREEM_PRODUCT_IDS_JSON = '{"pro":{"month":"prod-only"}}'
    monkeypatch.setattr(runtime.entry, "WorkerCreemGateway", no_provider)
    statements = trace_sql(runtime.store, monkeypatch)
    response = call(runtime, path, method="POST", body={"plan": "pro"}, headers=cookie())
    assert response.status == 503 and response.payload["error"]["code"] == "BILLING_UNAVAILABLE"
    assert statements == []


def test_valid_partial_cadence_still_verifies_provider_prices_and_refreshes_once(tmp_path):
    fixture, _, _ = seed(tmp_path / "configured.db")
    binding = D1ShapedSQLite(fixture.store)
    gateway = CreemStub()
    products = {"pro": {"month": "prod-pro-month"}, "max": {}}
    first = asyncio.run(read_or_refresh_catalog(binding=binding, gateway=gateway,
        headers={}, products=products, now=fixture.now))
    second = asyncio.run(read_or_refresh_catalog(binding=binding, gateway=gateway,
        headers={}, products=products, now=fixture.now + 1))
    assert first[0] == second[0] == 200
    assert first[1]["enabled"] is True and first[1]["provider"] == "creem"
    assert first[1]["plans"][1]["prices"]["month"]["amount"] == "29"
    assert first[1]["plans"][1]["prices"]["year"]["configured"] is False
    assert first[1]["plans"][2]["prices"]["month"]["amount"] is None
    assert gateway.calls == [("product", "prod-pro-month")]


def test_http_contract_explicit_empty_products_returns_free_without_catalog_database():
    class NoDatabase:
        def prepare(self, *args):
            raise AssertionError("Public Free catalog must not read/write D1")

    async def no_body():
        raise AssertionError("GET must not read request body")

    status, payload = asyncio.run(handle_http_request(method="GET", path="/billing/plan",
        headers={}, read_body=no_body, binding=NoDatabase(), creem_secret="",
        configured_products={}, now=NOW))
    assert status == 200 and payload["enabled"] is False

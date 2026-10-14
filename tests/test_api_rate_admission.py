"""Production REST frequency admission through native Workers rate limits."""
import asyncio
import importlib.util
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from deployment_config_fixture import configured_runtime
from norulo_server.cloudflare_auth_admission import API_RATE_LIMITS, api_admission
from test_worker_application_security import application, request
from test_worker_production_runtime import runtime  # noqa: F401 - pytest fixture


ROOT = Path(__file__).resolve().parents[1]
HEX = set("0123456789abcdef")


class Window:
    """A fixed-window stand-in for one native binding; it records only keys."""
    def __init__(self, limit=None, result=None, failure=False):
        self.limit_value, self.result, self.failure = limit, result, failure
        self.keys, self.counts = [], {}

    async def limit(self, options):
        key = options["key"]
        self.keys.append(key)
        if self.failure:
            raise RuntimeError("synthetic native diagnostic must not escape")
        if self.result is not None:
            return {"success": self.result}
        self.counts[key] = self.counts.get(key, 0) + 1
        return {"success": self.limit_value is None or self.counts[key] <= self.limit_value}


def production(**windows):
    env = SimpleNamespace(NORULO_MODE="production")
    for name, _, _ in API_RATE_LIMITS:
        setattr(env, name, windows.get(name, Window()))
    return env


def admit(env, headers):
    return asyncio.run(api_admission(env, SimpleNamespace(headers=headers)))


@pytest.mark.parametrize("mode", ["preview", "local", "", "unknown"])
def test_nonproduction_modes_read_no_rate_binding(mode):
    class Environment:
        NORULO_MODE = mode
        def __getattr__(self, name):
            raise AssertionError("nonproduction admission read " + name)
    assert asyncio.run(api_admission(Environment(), SimpleNamespace(headers={}))) is None


@pytest.mark.parametrize("missing", [name for name, _, _ in API_RATE_LIMITS])
def test_any_missing_binding_fails_closed_before_native_calls(missing):
    env = production()
    delattr(env, missing)
    decision = admit(env, {"cf-connecting-ip": "192.0.2.1", "cookie": "nr_session=ses-v2.synthetic"})
    assert decision[:2] == (503, {"error": {"code": "API_ADMISSION_UNAVAILABLE"}})
    assert decision[2] == {"Cache-Control": "no-store"}
    assert not any(getattr(env, name, Window()).keys for name, _, _ in API_RATE_LIMITS)


def test_anonymous_requests_use_only_hashed_network_windows():
    env = production()
    assert admit(env, {"cf-connecting-ip": "192.0.2.1", "authorization": "Basic ignored"}) is None
    ip_keys = env.API_IP_BURST_RATE_LIMIT.keys + env.API_IP_RATE_LIMIT.keys
    assert len(ip_keys) == 2 and ip_keys[0] == ip_keys[1]
    assert len(ip_keys[0]) == 64 and set(ip_keys[0]) <= HEX and "192.0.2.1" not in ip_keys[0]
    assert not env.API_CREDENTIAL_BURST_RATE_LIMIT.keys and not env.API_CREDENTIAL_RATE_LIMIT.keys


@pytest.mark.parametrize("headers", [
    {"authorization": "Bearer nrk_" + "A" * 43},
    {"authorization": "bearer ses-v2.synthetic"},
    {"x-norulo-api-key": "nrk_" + "B" * 43},
    {"cookie": 'theme=dark; nr_session="ses-v2.cookie"'},
])
def test_presented_credentials_share_a_bucket_across_networks(headers):
    env = production()
    for address in ("192.0.2.1", "198.51.100.7"):
        assert admit(env, {"cf-connecting-ip": address, **headers}) is None
    burst, sustained = env.API_CREDENTIAL_BURST_RATE_LIMIT.keys, env.API_CREDENTIAL_RATE_LIMIT.keys
    assert len(burst) == len(sustained) == 2 and len(set(burst + sustained)) == 1
    assert all(len(key) == 64 and set(key) <= HEX for key in burst)
    secret = next(iter(headers.values())).split()[-1].split("=")[-1].strip('"')
    assert secret not in burst[0]
    assert env.API_IP_RATE_LIMIT.keys[0] != env.API_IP_RATE_LIMIT.keys[1]


def test_distinct_credentials_and_ipv6_prefixes_are_keyed_independently():
    env = production()
    admit(env, {"cf-connecting-ip": "2001:db8:1:2::1", "cookie": "nr_session=one"})
    admit(env, {"cf-connecting-ip": "2001:db8:1:2:ffff::9", "cookie": "nr_session=two"})
    admit(env, {"cf-connecting-ip": "2001:db8:1:3::1"})
    ip = env.API_IP_RATE_LIMIT.keys
    assert ip[0] == ip[1] != ip[2]
    assert len(set(env.API_CREDENTIAL_RATE_LIMIT.keys)) == 2


@pytest.mark.parametrize("denied,retry_after,later", [
    ("API_IP_BURST_RATE_LIMIT", "10", ["API_IP_RATE_LIMIT", "API_CREDENTIAL_BURST_RATE_LIMIT", "API_CREDENTIAL_RATE_LIMIT"]),
    ("API_IP_RATE_LIMIT", "60", ["API_CREDENTIAL_BURST_RATE_LIMIT", "API_CREDENTIAL_RATE_LIMIT"]),
    ("API_CREDENTIAL_BURST_RATE_LIMIT", "10", ["API_CREDENTIAL_RATE_LIMIT"]),
    ("API_CREDENTIAL_RATE_LIMIT", "60", []),
])
def test_first_denied_window_returns_its_retry_interval_without_later_calls(denied, retry_after, later):
    env = production(**{denied: Window(result=False)})
    status, payload, headers = admit(env, {"cf-connecting-ip": "192.0.2.1",
                                           "x-norulo-api-key": "nrk_" + "C" * 43})
    assert status == 429 and payload["error"]["code"] == "API_RATE_LIMIT"
    assert headers == {"Cache-Control": "no-store", "Retry-After": retry_after}
    assert all(not getattr(env, name).keys for name in later)


@pytest.mark.parametrize("window", [Window(result="true"), Window(result=0), Window(failure=True)])
def test_uncertain_native_outcomes_fail_closed_without_retry(window):
    env = production(API_CREDENTIAL_RATE_LIMIT=window)
    decision = admit(env, {"cf-connecting-ip": "192.0.2.1", "cookie": "nr_session=ses-v2.synthetic"})
    assert decision[:2] == (503, {"error": {"code": "API_ADMISSION_UNAVAILABLE"}})
    assert "synthetic" not in json.dumps(decision) and len(window.keys) == 1


def test_burst_and_sustained_windows_bound_one_credential():
    env = production(API_CREDENTIAL_BURST_RATE_LIMIT=Window(limit=120),
                     API_CREDENTIAL_RATE_LIMIT=Window(limit=600))
    headers = {"cf-connecting-ip": "192.0.2.1", "cookie": "nr_session=ses-v2.synthetic"}
    assert all(admit(env, headers) is None for _ in range(120))
    assert admit(env, headers)[2]["Retry-After"] == "10"
    # Another credential behind the same network keeps its own allowance.
    assert admit(env, {**headers, "cookie": "nr_session=ses-v2.colleague"}) is None


@pytest.mark.parametrize("path", ["/api/v1/expenses", "/auth/email/request-code", "/webhooks/creem",
                                  "/api/v1/expenses/export?workspaceId=a&workspaceId=b"])
def test_worker_denial_precedes_parsing_bodies_identity_and_ledger(path):
    app, calls = application()
    app.env.NORULO_MODE = "production"
    for name, value in vars(production(API_IP_RATE_LIMIT=Window(result=False))).items():
        setattr(app.env, name, value)
    async def forbidden(**_):
        raise AssertionError("Rate-denied request reached identity or business work")
    app.fetch.__func__.__globals__["handle_identity_request"] = forbidden
    incoming = request(path, method="POST", headers={"cf-connecting-ip": "192.0.2.1"})
    async def forbidden_body():
        raise AssertionError("Rate-denied request read its body")
    incoming.bytes = forbidden_body
    response = asyncio.run(app.fetch(incoming))
    assert response.status == 429 and response.payload["error"]["code"] == "API_RATE_LIMIT"
    assert response.headers["Retry-After"] == "60" and calls == []


def test_admitted_production_request_reaches_the_ledger_handler():
    app, calls = application()
    app.env.NORULO_MODE = "production"
    env = production()
    for name, value in vars(env).items():
        setattr(app.env, name, value)
    response = asyncio.run(app.fetch(request("/api/v1/expenses", method="GET",
        headers={"cf-connecting-ip": "192.0.2.1", "authorization": "Bearer nrk_" + "D" * 43})))
    assert response.status == 204 and calls == ["ledger"]
    assert all(len(getattr(env, name).keys) == 1 for name, _, _ in API_RATE_LIMITS)


def test_paused_worker_returns_before_rate_admission():
    app, calls = application()
    app.env.NORULO_MODE, app.env.NORULO_D1_ACCESS_ENABLED = "production", "0"
    response = asyncio.run(app.fetch(request("/api/v1/expenses")))
    assert response.status == 503 and response.payload["error"]["code"] == "D1_ACCESS_PAUSED"


def _checker():
    spec = importlib.util.spec_from_file_location("api_rate_checker", ROOT / "scripts/check-ledger-s01.py")
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    return checker


def test_reviewed_production_windows_are_generous_and_isolated():
    checker = _checker()
    config = json.loads((ROOT / "cloudflare/server/wrangler.production.jsonc").read_text(encoding="utf-8"))
    assert config["ratelimits"] == checker.PRODUCTION_RATE_LIMITS
    reviewed = {item["name"]: item for item in checker.API_RATE_LIMITS}
    assert [(name, reviewed[name]["simple"]["period"]) for name, _, _ in API_RATE_LIMITS] == [
        (name, period) for name, _, period in API_RATE_LIMITS]
    namespaces = [item["namespace_id"] for item in config["ratelimits"]]
    assert len(set(namespaces)) == len(namespaces) and all(value.isdigit() for value in namespaces)
    limit = {name: item["simple"]["limit"] for name, item in reviewed.items()}
    # Burst windows allow more than the sustained per-second rate; shared
    # networks receive more room than one credential.
    assert limit["API_CREDENTIAL_BURST_RATE_LIMIT"] * 6 > limit["API_CREDENTIAL_RATE_LIMIT"]
    assert limit["API_IP_BURST_RATE_LIMIT"] * 6 > limit["API_IP_RATE_LIMIT"]
    assert limit["API_IP_RATE_LIMIT"] > limit["API_CREDENTIAL_RATE_LIMIT"] >= 600
    assert limit["API_IP_BURST_RATE_LIMIT"] > limit["API_CREDENTIAL_BURST_RATE_LIMIT"] >= 120


@pytest.mark.parametrize("change", ["missing", "limit", "period", "namespace", "auth-only"])
def test_guard_rejects_production_without_the_reviewed_api_windows(change):
    checker = _checker()
    config = configured_runtime("production")
    limits = config["ratelimits"]
    if change == "missing":
        del limits[-1]
    elif change == "limit":
        limits[1]["simple"]["limit"] = 1
    elif change == "period":
        limits[2]["simple"]["period"] = 10
    elif change == "namespace":
        limits[3]["namespace_id"] = limits[0]["namespace_id"]
    else:
        config["ratelimits"] = limits[:1]
    with tempfile.TemporaryDirectory() as directory:
        folder = Path(directory)
        (folder / "src").mkdir()
        (folder / "src/entry.py").touch()
        (folder / "wrangler.production.jsonc").write_text(json.dumps(config))
        with patch.object(checker, "SERVER", folder), pytest.raises(ValueError, match="API rate limits"):
            checker.validate_config("production", allow_placeholders=False)


def test_production_ingress_denial_never_reaches_d1(runtime):
    from test_worker_production_runtime import call, cookie

    class UntouchableDatabase:
        def __getattr__(self, name):
            raise AssertionError("Rate-denied production request reached D1")
    admitted = call(runtime, "/api/v1/me", headers=cookie())
    assert admitted.status == 200 and admitted.payload["id"] == "owner"
    runtime.worker.env.DB = UntouchableDatabase()
    runtime.worker.env.API_CREDENTIAL_RATE_LIMIT = Window(result=False)
    denied = call(runtime, "/api/v1/me", headers=cookie())
    assert denied.status == 429 and denied.payload["error"]["code"] == "API_RATE_LIMIT"
    assert denied.headers == {"Cache-Control": "no-store", "Retry-After": "60"}

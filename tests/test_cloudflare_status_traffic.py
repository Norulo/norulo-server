"""Status contracts and failure/cache isolation, with no real analytics or D1."""
import asyncio
import json
from types import SimpleNamespace

import pytest

from norulo_server import cloudflare_status_traffic as status
from test_worker_production_runtime import load_entry
from test_worker_application_security import request
from rate_limit_fixture import admitting_api_rate_limits

NOW = status.timestamp("2026-10-16T14:25:00Z")
ACCOUNT, TOKEN = "a" * 32, "synthetic-private-analytics-token"
ENV = SimpleNamespace(NORULO_MODE="local", NORULO_CF_ACCOUNT_ID=ACCOUNT, NORULO_CF_ANALYTICS_TOKEN=TOKEN)


class IO:
    def __init__(self, *, failure=None, scheduler_failure=False, cache_failure=False):
        self.calls, self.stored = [], {}
        self.failure, self.scheduler_failure, self.cache_failure = failure, scheduler_failure, cache_failure

    async def json(self, url, *, token="", body=None):
        self.calls.append((url, token, body))
        if url == status.MCP_HEALTH_URL:
            return {"ok": True}
        scheduler = "workersInvocationsScheduled" in body["query"]
        if self.failure or scheduler and self.scheduler_failure:
            raise self.failure or RuntimeError(TOKEN)
        start, _ = status.traffic_window(NOW)
        def row(script, index, requests, errors):
            return {"dimensions": {"scriptName": script, "datetimeHour": status.iso(start + index * status.HOUR)},
                    "sum": {"requests": requests, "errors": errors}}
        account = ({"workersInvocationsScheduled": [{"datetime": "2026-10-16T13:10:02Z", "status": "success"}]}
            if scheduler else {**{f"d{d}": [] for d in range(7)}, "d0": [row("norulo-web", 3, 12345, 0)],
            "d6": [row("norulo-web", 167, 40, 0), row("norulo-server-production", 150, 987, 99),
                   row("norulo-connect", 166, 77, 1), row("unrelated", 160, 55, 0)]})
        return {"data": {"viewer": {"accounts": [account]}}}

    async def match(self, key):
        if self.cache_failure:
            raise RuntimeError(TOKEN)
        return self.stored.get(key)

    async def put(self, key, body, expires, ttl):
        if self.cache_failure:
            raise RuntimeError(TOKEN)
        self.stored[key] = body, expires


@pytest.fixture(autouse=True)
def reset(monkeypatch):
    monkeypatch.setattr(status, "_memo", None)


def call(io, *, method="GET", env=ENV, now=NOW):
    return asyncio.run(status.status_traffic(method, env, io=io, now=now))


def test_public_contract_and_queries():
    io = IO()
    code, raw, headers = call(io)
    assert code == 200 and headers["Cache-Control"] == "public, max-age=300"
    for private in [TOKEN, ACCOUNT, "12345", "987", "norulo-server-production", "norulo-connect"]:
        assert private not in raw
    body = json.loads(raw)
    assert body["available"] and body["version"] == 1 and body["timezone"] == "UTC"
    assert body["windowEnd"] == "2026-10-16T15:00:00.000Z"
    assert body["scheduler"] == {"lastRunAt": "2026-10-16T13:10:02.000Z", "outcome": "success"}
    assert body["mcp"] == {"reachable": True}
    web, api, mcp = body["services"]
    assert [service["id"] for service in body["services"]] == ["web", "api", "mcp"]
    assert web["levels"][3] == 4 and 0 < web["levels"][167] < 4
    assert api["levels"][150] == 4 and api["errors"][150] == 2
    assert mcp["errors"][166] == 1
    for service in body["services"]:
        assert len(service["levels"]) == len(service["errors"]) == 168
        assert all(type(x) is int and 0 <= x <= 4 for x in service["levels"])
    query = next(body for _, _, body in io.calls if body and "workersInvocationsAdaptive" in body["query"])
    assert query["query"].count("workersInvocationsAdaptive") == 7
    assert query["variables"]["since0"] == "2026-10-09T15:00:00.000Z"
    assert query["variables"]["until6"] == body["windowEnd"]


@pytest.mark.parametrize("requests,peak,want", [(0, 100, 0), (1, 10000, 1), (50, 10000, 2), (10000, 10000, 4)])
def test_activity_levels(requests, peak, want):
    assert status.activity_level(requests, peak) == want


@pytest.mark.parametrize("requests,errors,want", [(100, 0, 0), (100, 1, 1), (100, 5, 2), (0, 1, 2)])
def test_error_levels(requests, errors, want):
    assert status.error_level(requests, errors) == want


@pytest.mark.parametrize("account,token", [(ACCOUNT, ""), ("bad", TOKEN), ("", TOKEN)])
def test_not_configured_still_probes_mcp(account, token):
    io = IO()
    env = SimpleNamespace(NORULO_CF_ACCOUNT_ID=account, NORULO_CF_ANALYTICS_TOKEN=token)
    body = json.loads(call(io, env=env)[1])
    assert body["reason"] == "not_configured" and body["mcp"]["reachable"]
    assert len(io.calls) == 1 and io.calls[0][0] == status.MCP_HEALTH_URL


def test_partial_failure_and_redacted_diagnostics(capsys):
    body = json.loads(call(IO(scheduler_failure=True))[1])
    assert body["available"] and body["scheduler"] is None
    assert TOKEN not in capsys.readouterr().out


@pytest.mark.parametrize("failure", [RuntimeError(TOKEN), status.AnalyticsFailure("http_failure", 403)])
def test_analytics_failure_is_unknown_not_zero(failure, capsys):
    io = IO(failure=failure)
    code, raw, headers = call(io)
    body = json.loads(raw)
    assert code == 200 and not body["available"] and body["services"] == []
    assert body["reason"] == "unavailable" and body["mcp"]["reachable"]
    assert headers["Cache-Control"] == "public, max-age=60"
    logs = capsys.readouterr().out
    assert TOKEN not in logs + raw and "NORULO_STATUS_ANALYTICS_FAILED" in logs
    assert len(io.calls) == 3


def test_cache_hits_expire_without_extending_stale_data(monkeypatch):
    io = IO()
    original = call(io)[1]
    assert call(io, now=NOW + 590)[1] == original and len(io.calls) == 3
    monkeypatch.setattr(status, "_memo", None)
    assert call(io, now=NOW + 595)[1] == original and len(io.calls) == 3
    assert call(io, now=NOW + 595)[2]["Cache-Control"] == "public, max-age=5"
    assert call(io, now=NOW + 601)[1] != original and len(io.calls) == 6


def test_cache_does_not_hide_new_configuration_or_rotated_credentials():
    io = IO()
    call(io, env=SimpleNamespace())
    assert json.loads(call(io)[1])["available"]
    rotated = SimpleNamespace(**{**vars(ENV), "NORULO_CF_ANALYTICS_TOKEN": "rotated-synthetic"})
    call(io, env=rotated)
    assert len(io.calls) == 7


def test_cache_failure_keeps_public_response_working():
    assert json.loads(call(IO(cache_failure=True))[1])["available"]


def test_head_reuses_get_cache_and_has_no_body():
    io = IO()
    call(io)
    code, raw, headers = call(io, method="HEAD")
    assert code == 200 and raw is None and headers["Cache-Control"] == "public, max-age=300"
    assert len(io.calls) == 3


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "OPTIONS"])
def test_methods_rejected_without_io(method):
    io = IO()
    assert call(io, method=method)[0] == 405 and not io.calls


@pytest.mark.parametrize("payload", [{"errors": [{"message": TOKEN}]}, {}, {"data": {"viewer": {"accounts": []}}}])
def test_graphql_rejects_provider_errors_and_missing_accounts(payload):
    class Broken:
        async def json(self, *args, **kwargs):
            return payload
    with pytest.raises(status.AnalyticsFailure) as error:
        asyncio.run(status.graphql(Broken(), TOKEN, "", {}))
    assert TOKEN not in str(error.value)


def test_missing_alias_is_not_healthy_empty_traffic():
    with pytest.raises(status.AnalyticsFailure):
        status.summarize_invocations({}, NOW)


@pytest.mark.parametrize("deny", [False, True])
def test_ingress_without_d1_preserves_production_admission(monkeypatch, deny):
    entry = load_entry()
    calls = []
    async def summary(method, env):
        calls.append(method)
        return 200, '{"version":1}', {"Cache-Control": "public, max-age=300"}
    monkeypatch.setattr(entry, "status_traffic", summary)
    env = SimpleNamespace(NORULO_MODE="production", NORULO_D1_ACCESS_ENABLED="0",
        **({} if deny else admitting_api_rate_limits()))
    instance = entry.Default.__new__(entry.Default)
    instance.env = env
    response = asyncio.run(instance.fetch(request("/status/traffic.json", method="GET")))
    assert response.status == (503 if deny else 200)
    assert calls == ([] if deny else ["GET"])

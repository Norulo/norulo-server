"""Execute the real Worker application class with inert FFI/provider boundaries."""
import ast
import asyncio
import json
import time
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit, parse_qs, unquote

import pytest

from norulo_server.cloudflare_plan_limits import PlanLimitError
from norulo_server.cloudflare_creem_gateway import CreemRequestRejected, catalog_product_bindings
from norulo_server.cloudflare_ledger_reports import CsvExport
from norulo_server.json_input import validate_json_unicode, decode_json_body
from norulo_server.cloudflare_auth_admission import api_admission, authorize_admission
from rate_limit_fixture import admitting_api_rate_limits


class Response:
    def __init__(self, payload=None, *, status=200, headers=None):
        self.payload, self.status, self.headers = payload, status, headers

    @classmethod
    def json(cls, payload, **options):
        return cls(payload, **options)


def application(*, same_site="Lax", catalog_failure=None, billing_failure=None,
                billing_gateway_failure=None):
    source = Path(__file__).resolve().parents[1] / "cloudflare/server/src/entry.py"
    tree = ast.parse(source.read_text())
    calls = []
    async def identity(**kwargs):
        return None
    async def ledger(**kwargs):
        calls.append("ledger")
        return 204, None
    async def catalog(**kwargs):
        raise catalog_failure
    async def billing(**kwargs):
        calls.append("billing")
        if billing_failure is not None:
            raise billing_failure
        return 200, {"accepted": True}
    def creem_gateway(env):
        if billing_gateway_failure is not None:
            raise billing_gateway_failure
        return None
    namespace = {"Response": Response, "time": time, "urlsplit": urlsplit,
        "parse_qs": parse_qs, "unquote": unquote, "json": json, "PlanLimitError": PlanLimitError,
        "handle_identity_request": identity, "handle_ledger_request": ledger,
        "read_or_refresh_catalog": catalog,
        "catalog_product_bindings": catalog_product_bindings,
        "handle_billing_mutation": billing, "validate_json_unicode": validate_json_unicode,
        "decode_json_body": decode_json_body,
        "api_admission": api_admission, "authorize_admission": authorize_admission,
        "CsvExport": CsvExport,
        "WorkerGitHubGateway": lambda _: None, "WorkerCreemGateway": creem_gateway}
    target = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_request_target")
    exec(compile(ast.Module(body=[target], type_ignores=[]), str(source), "exec"), namespace)
    node = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "_Application")
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), namespace)
    instance = namespace["_Application"].__new__(namespace["_Application"])
    instance.env = SimpleNamespace(NORULO_D1_ACCESS_ENABLED="1", NORULO_COOKIE_SAME_SITE=same_site,
        NORULO_APP_URL="https://app.example.test", NORULO_MODE="preview")
    instance.binding = SimpleNamespace(now=0)
    instance.jev_gateway = None
    return instance, calls


def request(path="/api/v1/expenses", *, method="POST", headers=None, raw=b"{}"):
    async def body():
        return raw
    return SimpleNamespace(url="https://api.example.test" + path, method=method,
        headers=headers or {}, bytes=body)


@pytest.mark.parametrize("same_site", ["Lax", "Strict", "None"])
@pytest.mark.parametrize("origin", [None, "https://hostile.example.test"])
@pytest.mark.parametrize("authorization", [None, "Basic invalid", "Bearer"])
@pytest.mark.parametrize("path,method", [
    ("/api/v1/expenses", "POST"),
    ("/api/v1/account/jev", "PATCH"),
    ("/api/v1/expense-recurring-rules", "POST"),
    ("/api/v1/expense-recurring-rules/rule_1", "PATCH"),
    ("/api/v1/expense-recurring-rules/rule_1", "DELETE"),
])
def test_cookie_writes_require_trusted_origin_for_every_samesite_mode(same_site, origin, authorization, path, method):
    app, calls = application(same_site=same_site)
    headers = {"cookie": "nr_session=synthetic"}
    if origin:
        headers["origin"] = origin
    if authorization:
        headers["authorization"] = authorization
    incoming = request(path, method=method, headers=headers)
    async def forbidden_body():
        raise AssertionError("Untrusted Cookie write read its body")
    incoming.bytes = forbidden_body
    response = asyncio.run(app.fetch(incoming))
    assert response.status == 403 and response.payload["error"]["code"] == "UNTRUSTED_ORIGIN"
    assert calls == []


@pytest.mark.parametrize("path,method", [
    ("/api/v1/expense-recurring-rules", "POST"),
    ("/api/v1/expense-recurring-rules/rule_1", "PATCH"),
    ("/api/v1/expense-recurring-rules/rule_1", "DELETE"),
])
def test_trusted_recurring_cookie_writes_reach_the_ledger_handler(path, method):
    app, calls = application()
    response = asyncio.run(app.fetch(request(path, method=method,
        headers={"cookie": "nr_session=synthetic", "origin": "https://app.example.test"})))
    assert response.status == 204 and calls == ["ledger"]
    assert response.headers["Cache-Control"] == "no-store"


def test_account_preference_cookie_write_rejects_too_many_sessions_before_body_or_handler():
    app, calls = application()
    incoming = request("/api/v1/account/jev", method="PATCH", headers={
        "cookie": "; ".join("nr_session=synthetic" + str(value) for value in range(9)),
        "origin": "https://app.example.test"})
    async def forbidden_body():
        raise AssertionError("Ambiguous credential write read its body")
    incoming.bytes = forbidden_body
    response = asyncio.run(app.fetch(incoming))
    assert response.status == 400 and response.payload == {"error": {"code": "AMBIGUOUS_AUTH"}}
    assert calls == []


@pytest.mark.parametrize("path,method", [
    ("/api/v1/expense-recurring-rules", "POST"),
    ("/api/v1/expense-recurring-rules/rule_1", "PATCH"),
])
@pytest.mark.parametrize("raw,status,code", [
    (b'{"schedule":', 422, "INVALID_INPUT"),
    (b'\xff', 422, "INVALID_INPUT"),
    (b'{"purpose":"\\ud800"}', 422, "INVALID_INPUT"),
    (b'{"schedule":{"\\udfff":true}}', 422, "INVALID_INPUT"),
    (b"[" * 4000 + b"]" * 4000, 422, "INVALID_INPUT"),
    (b"x" * 8193, 413, "REQUEST_TOO_LARGE"),
])
def test_recurring_body_safety_fails_before_business_dispatch(path, method, raw, status, code):
    app, calls = application()
    response = asyncio.run(app.fetch(request(path, method=method, raw=raw,
        headers={"cookie": "nr_session=synthetic", "origin": "https://app.example.test"})))
    assert response.status == status and response.payload == {"error": {"code": code}}
    assert response.headers["Cache-Control"] == "no-store"
    assert calls == []


def test_trusted_cookie_write_and_external_key_write_remain_supported():
    app, calls = application()
    assert asyncio.run(app.fetch(request(headers={"cookie": "nr_session=synthetic",
        "origin": "https://app.example.test"}))).status == 204
    assert asyncio.run(app.fetch(request(headers={"authorization": "Bearer nrk_synthetic"}))).status == 204
    assert calls == ["ledger", "ledger"]


def test_preview_catalog_diagnostics_never_return_provider_exception_text():
    class JsException(Exception):
        pass
    app, _ = application(catalog_failure=JsException("provider body includes unregistered_secret_value"))
    response = asyncio.run(app.fetch(request("/billing/plan", method="GET")))
    assert response.status == 503
    assert "unregistered_secret_value" not in json.dumps(response.payload)
    assert "transportDiagnostic" not in response.payload["error"]


@pytest.mark.parametrize("error", [
    CreemRequestRejected("provider rejected secret_provider_payload"),
    ValueError("unknown provider outcome secret_provider_payload"),
    TimeoutError("lost provider acknowledgement secret_provider_payload"),
    UnicodeError("invalid provider response secret_provider_payload"),
])
def test_billing_provider_failures_are_service_errors_without_exposing_provider_payloads(error):
    app, calls = application(billing_failure=error)
    response = asyncio.run(app.fetch(request("/billing/change-interval", raw=b'{"plan":"max","interval":"year"}')))
    assert response.status == 503 and response.payload == {"error": {"code": "BILLING_UNAVAILABLE"}}
    assert response.headers["Cache-Control"] == "no-store"
    assert "secret_provider_payload" not in json.dumps(response.payload)
    assert calls == ["billing"]


def test_billing_gateway_configuration_failure_is_a_service_error():
    app, calls = application(billing_gateway_failure=ValueError("provider origin invalid"))
    response = asyncio.run(app.fetch(request("/billing/checkout-sessions")))
    assert response.status == 503 and response.payload == {"error": {"code": "BILLING_UNAVAILABLE"}}
    assert calls == []


@pytest.mark.parametrize("raw", [b'{"plan":', b'\xff', b'{"plan":"\\ud800"}',
    b"[" * 4000 + b"]" * 4000])
def test_malformed_billing_input_remains_a_request_error_before_provider_dispatch(raw):
    app, calls = application(billing_failure=AssertionError("provider must not be called"))
    response = asyncio.run(app.fetch(request("/billing/checkout-sessions", raw=raw)))
    assert response.status == 422 and response.payload == {"error": {"code": "INVALID_REQUEST"}}
    assert calls == []


@pytest.mark.parametrize("path,status,code", [
    ("/api/v1/expenses?cursor=" + "x" * 8193, 413, "REQUEST_TOO_LARGE"),
    ("/api/v1/expenses/" + "x" * 8193, 413, "REQUEST_TOO_LARGE"),
    ("/api/v1/expenses/" + "%61" * 3000, 413, "REQUEST_TOO_LARGE"),
    ("/api/v1/expenses?cursor=%ED%A0%80", 422, "INVALID_INPUT"),
    ("/api/v1/expenses?cursor=%00", 422, "INVALID_INPUT"),
    ("/api/v1/expenses/%00", 422, "INVALID_INPUT"),
    ("/api/v1/expenses?" + "&".join("x=" for _ in range(101)), 422, "INVALID_INPUT"),
])
def test_invalid_url_inputs_are_rejected_before_application_dispatch(path, status, code):
    app, calls = application()
    response = asyncio.run(app.fetch(request(path, method="GET")))
    assert response.status == status and response.payload == {"error": {"code": code}}
    assert calls == []


def test_valid_encoded_emoji_query_reaches_application():
    app, calls = application()
    response = asyncio.run(app.fetch(request("/api/v1/expenses?cursor=%F0%9F%98%80", method="GET")))
    assert response.status == 204 and calls == ["ledger"]


@pytest.mark.parametrize("path", ["/api/v1/expenses", "/billing/checkout-sessions"])
def test_chunked_oversized_body_stops_before_copy_or_business_dispatch(path):
    app, calls = application()
    class OversizedChunk:
        byteLength = 100_000_000
        def to_bytes(self):
            raise AssertionError("Oversized body was copied")
    class Reader:
        cancelled = released = False
        async def read(self):
            return SimpleNamespace(done=False, value=OversizedChunk())
        async def cancel(self):
            self.cancelled = True
        def releaseLock(self):
            self.released = True
    reader = Reader()
    incoming = request(path, headers={"origin": "https://app.example.test"})
    incoming.body = SimpleNamespace(getReader=lambda: reader)
    async def forbidden_buffer():
        raise AssertionError("Chunked body used an unbounded buffer")
    incoming.bytes = forbidden_buffer
    response = asyncio.run(app.fetch(incoming))
    assert response.status == 413 and calls == []
    assert reader.cancelled and reader.released


def test_chunked_json_body_preserves_valid_input_and_releases_reader():
    app, calls = application()
    class Reader:
        released = False
        chunks = iter((b'{"a":', b'1}'))
        async def read(self):
            chunk = next(self.chunks, None)
            return SimpleNamespace(done=chunk is None, value=chunk)
        async def cancel(self):
            raise AssertionError("Valid body was cancelled")
        def releaseLock(self):
            self.released = True
    reader = Reader()
    incoming = request()
    incoming.body = SimpleNamespace(getReader=lambda: reader)
    response = asyncio.run(app.fetch(incoming))
    assert response.status == 204 and calls == ["ledger"] and reader.released


@pytest.mark.parametrize("path", ["/auth/github/authorize", "/integrations/github/authorize"])
def test_production_github_rate_denial_precedes_identity_and_state_work(path):
    app, calls = application()
    app.env.NORULO_MODE = "production"
    admitted = []
    async def limit(options):
        admitted.append(options["key"])
        return {"success": False}
    app.env.AUTH_RATE_LIMIT = SimpleNamespace(limit=limit)
    for name, limiter in admitting_api_rate_limits().items():
        setattr(app.env, name, limiter)
    async def forbidden_identity(**_):
        raise AssertionError("Rate-denied request reached state/provider work")
    app.fetch.__func__.__globals__["handle_identity_request"] = forbidden_identity
    response = asyncio.run(app.fetch(request(path, method="GET",
        headers={"cf-connecting-ip": "2001:db8:1234::1"})))
    assert response.status == 429 and calls == []
    assert response.headers["Retry-After"] == "60"
    assert len(admitted) == 1 and len(admitted[0]) == 64


def test_github_callback_preserves_both_session_and_browser_clear_cookies():
    app, _ = application()
    cookies = ["nr_session=ses-v2.synthetic; Secure; HttpOnly",
               "nr_github_oauth=; Secure; HttpOnly; Max-Age=0"]
    async def identity(**_):
        return 302, None, {"Location": "https://app.example.test/projects",
                           "Set-Cookie": cookies, "Cache-Control": "no-store"}
    app.fetch.__func__.__globals__["handle_identity_request"] = identity
    response = asyncio.run(app.fetch(request("/auth/github/callback", method="GET")))
    assert response.status == 302
    assert [value for name, value in response.headers if name == "Set-Cookie"] == cookies


@pytest.mark.parametrize("path,headers", [
    ("/api/v1/expenses/export?workspaceId=owner&workspaceId=other", {}),
    ("/api/v1/expenses/export?workspaceId=owner", {"x-norulo-workspace": "other"}),
    ("/api/v1/me?workspaceId=", {}),
])
def test_conflicting_ledger_selectors_fail_before_authentication(path, headers):
    app, calls = application()
    response = asyncio.run(app.fetch(request(path, method="GET", headers=headers)))
    assert response.status == 422 and response.payload["error"]["code"] == "INVALID_INPUT"
    assert calls == []


@pytest.mark.parametrize("path", ["/api/v1/workspaces/owner/invites", "/api/v1/workspaces/owner/members/editor", "/api/v1/workspace-invitations/accept"])
def test_workspace_cookie_operations_require_trusted_origin_before_body_or_database(path):
    app, calls = application()
    response = asyncio.run(app.fetch(request(path, headers={"cookie": "nr_session=synthetic", "origin": "https://hostile.test"})))
    assert response.status == 403 and response.payload["error"]["code"] == "UNTRUSTED_ORIGIN"
    assert calls == []


@pytest.mark.parametrize("path,method", [
    ("/api/v1/workspace-invitation-requests", "GET"),
    ("/api/v1/workspaces/owner/invites/link/requests", "GET"),
    ("/api/v1/workspaces/owner/join-requests", "GET"),
    ("/api/v1/workspaces/owner/invites/link/requests/request/approve", "POST"),
    ("/api/v1/workspaces/owner/invites/link/requests/request/reject", "POST"),
])
def test_inviter_inbox_and_approval_routes_reach_the_ledger_handler(path, method):
    app, calls = application()
    response = asyncio.run(app.fetch(request(path, method=method,
        headers={"cookie": "nr_session=synthetic", "origin": "https://app.example.test"})))
    assert response.status == 204 and calls == ["ledger"]
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_invitation_reviews_reject_untrusted_cookie_origin_before_database(decision):
    app, calls = application()
    response = asyncio.run(app.fetch(request(
        "/api/v1/workspaces/owner/invites/link/requests/request/" + decision,
        headers={"cookie": "nr_session=synthetic", "origin": "https://hostile.test"})))
    assert response.status == 403 and response.payload["error"]["code"] == "UNTRUSTED_ORIGIN"
    assert calls == []

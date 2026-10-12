"""Production OTP admission is isolated, persistent and fail closed, locally."""
import asyncio
import hashlib
import sqlite3
from types import SimpleNamespace

import pytest

from test_worker_cost_pause import load_entry
from test_cloudflare_email_auth import Binding, Store, Gateway, SECRET, NOW
from test_worker_email_auth import incoming
from norulo_server.cloudflare_email_admission import (
    EMAIL_ADMISSION_SCOPE, email_ip_subject, require_email_admission,
)
from norulo_server.cloudflare_preview_rate import EmailRateLimit


def subject(value):
    return hashlib.sha256(value.encode()).hexdigest()


EMAIL, IP = subject("alice@example.test"), subject("192.0.2.1")


def production_env(**changes):
    return SimpleNamespace(NORULO_MODE="production", NORULO_D1_ACCESS_ENABLED="1",
        NORULO_EMAIL_AUTH_ENABLED="1", **changes)


class LocalStorage:
    """Actual SQLite transactions, without remote D1 or provider operations."""
    def __init__(self, connection):
        self.connection = connection
        self.sql = self
        self.queries, self.transactions = [], 0
        self.failure = None
        self.post_commit_failure = False

    def exec(self, query, *params):
        self.queries.append((query, params))
        if self.failure and self.failure(query):
            raise RuntimeError("private storage diagnostic")
        cursor = self.connection.execute(query, params)
        names = [column[0] for column in cursor.description or []]
        rows = [SimpleNamespace(**dict(zip(names, row))) for row in cursor.fetchall()]
        return SimpleNamespace(one=lambda: rows[0], toArray=lambda: rows)

    def transactionSync(self, callback):
        self.transactions += 1
        self.connection.execute("BEGIN")
        try:
            result = callback()
        except BaseException:
            self.connection.rollback()
            raise
        self.connection.commit()
        if self.post_commit_failure:
            raise RuntimeError("unknown outcome private diagnostic")
        return result


@pytest.fixture
def runtime(monkeypatch):
    connection = sqlite3.connect(":memory:", isolation_level=None)
    entry = load_entry()
    storage = LocalStorage(connection)
    monkeypatch.setattr(entry.time, "time", lambda: 120)
    env = production_env()
    try:
        yield SimpleNamespace(entry=entry, storage=storage, connection=connection,
            env=env, do=entry.EmailAdmission(SimpleNamespace(storage=storage), env))
    finally:
        connection.close()


def admit(runtime, kind="send", email=EMAIL, ip=IP, coordinator=None):
    return asyncio.run((coordinator or runtime.do).admitEmail(kind, email, ip))


def snapshot(runtime):
    return [tuple(row) for row in runtime.connection.execute("SELECT * FROM email_rate_clock")], [
        tuple(row) for row in runtime.connection.execute("SELECT * FROM email_request_rates ORDER BY subject")]


class UntouchableStorage:
    def __getattr__(self, name):
        raise AssertionError("rejected admission touched storage")


@pytest.mark.parametrize("change", [
    {"NORULO_MODE": "preview"}, {"NORULO_MODE": "local"}, {"NORULO_MODE": ""},
    {"NORULO_D1_ACCESS_ENABLED": "0"}, {"NORULO_EMAIL_AUTH_ENABLED": "0"},
    {"NORULO_EMAIL_AUTH_ENABLED": "true"},
])
def test_paused_or_nonproduction_admission_does_not_initialize_storage(change):
    entry = load_entry()
    env = production_env()
    for key, value in change.items():
        setattr(env, key, value)
    coordinator = entry.EmailAdmission(SimpleNamespace(storage=UntouchableStorage()), env)
    assert asyncio.run(coordinator.admitEmail("send", EMAIL, IP)) == {
        "ok": False, "error": "EMAIL_AUTH_NOT_CONFIGURED"}
    assert coordinator.rate_limiter is None


@pytest.mark.parametrize("kind,email,ip", [
    ("unknown", EMAIL, IP), ([], EMAIL, IP), ("send", "alice@example.test", IP),
    ("send", "A" * 64, IP), ("verify", "a" * 63, IP), ("verify", EMAIL, "192.0.2.1"),
    ("send", EMAIL, None), ("verify", EMAIL, "g" * 64),
])
def test_invalid_rpc_arguments_are_rejected_before_storage(kind, email, ip):
    entry = load_entry()
    coordinator = entry.EmailAdmission(SimpleNamespace(storage=UntouchableStorage()), production_env())
    assert asyncio.run(coordinator.admitEmail(kind, email, ip)) == {
        "ok": False, "error": "EMAIL_ADMISSION_UNAVAILABLE"}
    assert coordinator.rate_limiter is None


def test_production_namespace_only_contains_email_counters(runtime):
    assert admit(runtime) == {"ok": True}
    tables = {row[0] for row in runtime.connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert tables == {"email_rate_clock", "email_request_rates"}
    assert runtime.storage.transactions == 1
    assert len(snapshot(runtime)[1]) == 3
    assert "alice@example.test" not in repr(snapshot(runtime))
    assert "192.0.2.1" not in repr(snapshot(runtime))


def test_cooldown_rejection_and_restart_preserve_all_counters(runtime, monkeypatch):
    assert admit(runtime) == {"ok": True}
    before, changes = snapshot(runtime), runtime.connection.total_changes
    monkeypatch.setattr(runtime.entry.time, "time", lambda: 121)
    restarted = runtime.entry.EmailAdmission(SimpleNamespace(storage=runtime.storage), runtime.env)
    assert admit(runtime, ip=subject("new-ip"), coordinator=restarted) == {"ok": False, "retryAfter": 59}
    assert snapshot(runtime) == before
    # Initialization may issue INSERT OR IGNORE on restart, but no counter changes.
    assert runtime.connection.total_changes == changes
    monkeypatch.setattr(runtime.entry.time, "time", lambda: 180)
    assert admit(runtime, coordinator=restarted) == {"ok": True}


def test_send_hour_and_verify_ip_limits_survive_rotated_subjects(runtime, monkeypatch):
    for index in range(6):
        monkeypatch.setattr(runtime.entry.time, "time", lambda index=index: 120 + index * 60)
        assert admit(runtime, ip=subject(str(index))) == {"ok": True}
    monkeypatch.setattr(runtime.entry.time, "time", lambda: 480)
    assert admit(runtime, ip=subject("fresh-ip")) == {"ok": False, "retryAfter": 3120}
    for index in range(10):
        assert admit(runtime, "verify", email=subject(str(index))) == {"ok": True}
    before = snapshot(runtime)
    assert admit(runtime, "verify", email=subject("fresh-email")) == {"ok": False, "retryAfter": 60}
    assert snapshot(runtime) == before
    monkeypatch.setattr(runtime.entry.time, "time", lambda: 540)
    assert admit(runtime, "verify", email=subject("fresh-email")) == {"ok": True}


def test_competing_rpc_calls_cannot_oversubscribe_a_bucket(runtime):
    async def compete():
        return await asyncio.gather(*(runtime.do.admitEmail("verify", subject(str(index)), IP)
                                     for index in range(11)))
    results = asyncio.run(compete())
    assert results.count({"ok": True}) == 10
    assert results.count({"ok": False, "retryAfter": 60}) == 1
    assert sum(row[2] for row in snapshot(runtime)[1]) == 20


def test_storage_failure_rolls_back_clock_cleanup_and_reservation(runtime, monkeypatch):
    assert admit(runtime, "verify") == {"ok": True}
    before = snapshot(runtime)
    monkeypatch.setattr(runtime.entry.time, "time", lambda: 180)
    runtime.storage.failure = lambda query: query.startswith("INSERT INTO email_request_rates")
    assert admit(runtime, "verify", email=subject("new-email"), ip=subject("new-ip")) == {
        "ok": False, "error": "EMAIL_ADMISSION_UNAVAILABLE"}
    assert snapshot(runtime) == before


def test_unknown_transaction_response_has_no_refund_or_automatic_retry(runtime):
    runtime.storage.post_commit_failure = True
    assert admit(runtime) == {"ok": False, "error": "EMAIL_ADMISSION_UNAVAILABLE"}
    before = snapshot(runtime)
    assert runtime.storage.transactions == 1
    runtime.storage.post_commit_failure = False
    assert admit(runtime) == {"ok": False, "retryAfter": 60}
    assert snapshot(runtime) == before
    assert not hasattr(runtime.do, "refund") and not hasattr(runtime.do, "reset")


def test_production_and_preview_rpc_cannot_use_one_anothers_storage():
    entry = load_entry()
    preview = entry.ValidationBudget(SimpleNamespace(storage=UntouchableStorage()), production_env())
    assert asyncio.run(preview.admitEmail("send", EMAIL, IP)) == {
        "ok": False, "error": "EMAIL_AUTH_NOT_CONFIGURED"}
    production = entry.EmailAdmission(SimpleNamespace(storage=UntouchableStorage()),
        SimpleNamespace(NORULO_MODE="preview", NORULO_D1_ACCESS_ENABLED="1",
            NORULO_EMAIL_AUTH_ENABLED="1", NORULO_PREVIEW_PRODUCT_ENABLED="1"))
    assert asyncio.run(production.admitEmail("send", EMAIL, IP))["ok"] is False


def test_http_admission_has_no_effect_or_diagnostics():
    entry = load_entry()
    coordinator = entry.EmailAdmission(SimpleNamespace(storage=UntouchableStorage()), production_env())
    payload, options = asyncio.run(coordinator.fetch(SimpleNamespace()))
    assert options["status"] == 405 and payload == {"error": {"code": "METHOD_NOT_ALLOWED"}}
    assert coordinator.rate_limiter is None


@pytest.mark.parametrize("result", [None, {}, {"ok": "false"}, {"ok": 1}, {"ok": "true"},
    {"ok": False}, {"ok": True, "error": "uncertain"}, {"ok": True, "retryAfter": 1},
    {"ok": False, "error": "unknown", "retryAfter": 1},
    *({"ok": False, "retryAfter": value} for value in [None, True, "60", 0, -1, 3601, 1.5,
       float("nan"), float("inf"), float("-inf")])])
def test_rpc_result_requires_exact_success_or_bounded_known_rate_limit(result):
    with pytest.raises(RuntimeError, match="^EMAIL_ADMISSION_UNAVAILABLE$"):
        require_email_admission(result)


@pytest.mark.parametrize("result", [{"ok": True}, SimpleNamespace(ok=True)])
def test_rpc_result_accepts_definite_success(result):
    assert require_email_admission(result) is True


@pytest.mark.parametrize("retry_after", [1, 60.0, 3600])
def test_rpc_result_accepts_only_integral_retry_after(retry_after):
    with pytest.raises(EmailRateLimit) as caught:
        require_email_admission(SimpleNamespace(ok=False, retryAfter=retry_after))
    assert caught.value.retry_after == retry_after


class Namespace:
    def __init__(self, coordinator):
        self.coordinator = coordinator
        self.names, self.calls = [], []
        self.failure = False
        self.result = None

    def idFromName(self, name):
        self.names.append(name)
        return "fixed-email-admission"

    def get(self, identity):
        assert identity == "fixed-email-admission"
        async def admit(kind, email_subject, ip_subject):
            self.calls.append((kind, email_subject, ip_subject))
            if self.failure:
                raise self.failure("private RPC provider diagnostic")
            if self.result is not None:
                return self.result
            return await self.coordinator.admitEmail(kind, email_subject, ip_subject)
        return SimpleNamespace(admitEmail=admit)


def test_remote_adapter_uses_only_fixed_production_namespace(runtime):
    namespace = Namespace(runtime.do)
    runtime.env.EMAIL_ADMISSION = namespace
    runtime.env.VALIDATION_BUDGET = UntouchableStorage()
    request = incoming("/auth/email/request-code", body={})
    request.headers.update({"cf-connecting-ip": "192.0.2.1", "x-forwarded-for": "hostile"})
    adapter = runtime.entry._remote_email_admission(runtime.env, request)
    assert asyncio.run(adapter("send", EMAIL)) is True
    assert namespace.names == [EMAIL_ADMISSION_SCOPE]
    assert namespace.calls == [("send", EMAIL, runtime.entry._email_ip_subject(request))]
    assert all("192.0.2.1" not in value for value in namespace.calls[0])


def test_missing_production_namespace_never_falls_back_to_preview(runtime):
    runtime.env.VALIDATION_BUDGET = UntouchableStorage()
    assert runtime.entry._remote_email_admission(runtime.env, SimpleNamespace()) is None


@pytest.mark.parametrize("mode", ["preview", "local", "unknown"])
def test_nonproduction_adapter_does_not_read_any_namespace(runtime, mode):
    class Environment:
        NORULO_MODE = mode
        def __getattr__(self, name):
            raise AssertionError("nonproduction adapter read binding")
    assert runtime.entry._remote_email_admission(Environment(), SimpleNamespace()) is None


@pytest.fixture
def application(runtime, tmp_path, monkeypatch):
    binding, gateway = Binding(Store(tmp_path / "production-identity.sqlite")), Gateway()
    namespace = Namespace(runtime.do)
    runtime.env.NORULO_APP_URL = "https://norulo.com"
    runtime.env.NORULO_ALLOWED_ORIGINS = "https://norulo.com"
    runtime.env.NORULO_EMAIL_CODE_SECRET = SECRET
    runtime.env.NORULO_COOKIE_SAME_SITE = "None"
    runtime.env.EMAIL_ADMISSION = namespace
    runtime.env.DB = binding
    monkeypatch.setattr(runtime.entry, "NativeD1", lambda value: value)
    monkeypatch.setattr(runtime.entry, "WorkerEmailGateway", lambda _: gateway)
    monkeypatch.setattr(runtime.entry.time, "time", lambda: NOW)
    worker = runtime.entry.Default()
    worker.env = runtime.env
    return SimpleNamespace(worker=worker, binding=binding, gateway=gateway,
        namespace=namespace, entry=runtime.entry)


def test_production_ingress_signin_uses_independent_admission_and_one_use_code(application):
    request = incoming("/auth/email/request-code", origin="https://norulo.com",
        body={"email": "alice@example.test", "purpose": "login"})
    request.headers["cf-connecting-ip"] = "192.0.2.1"
    payload, options = asyncio.run(application.worker.fetch(request))
    assert options["status"] == 202
    cookie = options["headers"]["Set-Cookie"].split(";", 1)[0]
    code = application.gateway.sent[0][1]
    verification = incoming("/auth/email/verify-code", origin="https://norulo.com", cookie=cookie,
        body={"email": "alice@example.test", "challengeId": payload["challengeId"], "code": code})
    verification.headers["cf-connecting-ip"] = "192.0.2.1"
    result, verified = asyncio.run(application.worker.fetch(verification))
    assert verified["status"] == 200 and result["authenticated"] is True
    assert result["user"]["emailVerified"] is True
    assert verified["headers"]["Set-Cookie"].startswith("nr_session=")
    replay, rejected = asyncio.run(application.worker.fetch(verification))
    assert rejected["status"] == 400 and replay["error"]["code"] == "EMAIL_CODE_INVALID"
    assert application.namespace.names == [EMAIL_ADMISSION_SCOPE] * 2
    assert [call[0] for call in application.namespace.calls] == ["send", "verify"]


def test_random_no_challenge_verifications_cannot_fill_production_subject_table(application, runtime):
    async def attack():
        for index in range(10_200):
            request = incoming("/auth/email/verify-code", origin="https://norulo.com",
                cookie="nr_email_challenge=" + "A" * 43,
                body={"email": f"random-{index}@example.test", "challengeId": "A" * 43, "code": "123456"})
            request.headers["cf-connecting-ip"] = f"2001:db8:{index:x}::1"
            payload, options = await application.worker.fetch(request)
            assert options["status"] == 400 and payload["error"]["code"] == "EMAIL_CODE_INVALID"
    asyncio.run(attack())
    assert not application.namespace.calls and not application.namespace.names
    assert not runtime.storage.queries and not application.binding.groups
    assert not application.gateway.sent
    # A legitimate new challenge still has room after the original attack size.
    payload, options = asyncio.run(application.worker.fetch(incoming("/auth/email/request-code",
        origin="https://norulo.com", body={"email": "alice@example.test", "purpose": "login"})))
    assert options["status"] == 202 and len(application.gateway.sent) == 1
    assert len(snapshot(runtime)[1]) == 3


def test_rotating_ipv6_hosts_share_send_cap_without_exhausting_global_admission(runtime):
    prefix_subject = email_ip_subject("2001:db8:1234:5678::1")
    accepted = 0
    for index in range(600):
        ip = email_ip_subject(f"2001:db8:1234:5678::{index + 1:x}")
        assert ip == prefix_subject
        result = admit(runtime, email=subject(f"synthetic-{index}@example.test"), ip=ip)
        if result == {"ok": True}:
            accepted += 1
        else:
            assert result == {"ok": False, "retryAfter": 3480}
    assert accepted == 30 and len(snapshot(runtime)[1]) == 32
    assert admit(runtime, email=subject("legitimate@example.test"),
        ip=email_ip_subject("2001:db8:1234:5679::1")) == {"ok": True}


@pytest.mark.parametrize("one,two", [
    ("2001:db8:1234:5678::1", "2001:0DB8:1234:5678:ffff:ffff:ffff:ffff"),
    ("192.0.2.1", "::ffff:192.0.2.1"),
    (None, "bad ingress value"),
    ("bad ingress value", "2001:db8::1%client-selected-zone"),
])
def test_email_ip_subject_normalizes_equivalent_addresses_and_invalid_fallback(one, two):
    assert email_ip_subject(one) == email_ip_subject(two)
    assert len(email_ip_subject(one)) == 64


@pytest.mark.parametrize("one,two", [
    ("192.0.2.1", "192.0.2.2"),
    ("2001:db8:1234:5678::1", "2001:db8:1234:5679::1"),
    ("192.0.2.1", "not an IP"),
])
def test_distinct_ipv4_addresses_and_ipv6_prefixes_keep_independent_admission(one, two):
    assert email_ip_subject(one) != email_ip_subject(two)


@pytest.mark.parametrize("failure", [RuntimeError, ValueError, "malformed"])
def test_production_rpc_failure_blocks_mail_and_d1_without_retry(application, failure):
    application.namespace.failure = failure if failure != "malformed" else False
    if failure == "malformed":
        application.namespace.result = {"ok": "true"}
    payload, options = asyncio.run(application.worker.fetch(incoming("/auth/email/request-code",
        origin="https://norulo.com", body={"email": "alice@example.test", "purpose": "login"})))
    assert options["status"] == 503 and payload == {"error": {"code": "EMAIL_AUTH_UNAVAILABLE"}}
    assert len(application.namespace.calls) == 1
    assert not application.gateway.sent and application.binding.reads == 0 and not application.binding.groups


def test_invalid_public_request_is_rejected_before_admission_d1_or_provider(application):
    payload, options = asyncio.run(application.worker.fetch(incoming("/auth/email/request-code",
        origin="https://norulo.com", body={"email": "invalid", "purpose": "login"})))
    assert options["status"] == 422 and payload["error"]["code"] == "INVALID_INPUT"
    assert not application.namespace.calls and not application.gateway.sent
    assert application.binding.reads == 0 and not application.binding.groups

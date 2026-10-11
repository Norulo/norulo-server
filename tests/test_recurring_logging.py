"""Production cron receipts expose aggregate outcomes without changing execution."""
import asyncio
import copy
import json
import sys
from types import SimpleNamespace

import pytest

from norulo_server.cloudflare_recurring_scheduler import (
    PRODUCTION_RECURRING_CRON, RECURRING_SCHEDULER_SCOPE,
    log_recurring_receipt, recurring_log_receipts,
)
from test_worker_production_runtime import load_entry


SCHEDULED = 1_800_000_000_000
HEALTHY = {"ok": True, "scanned": 3, "created": 3, "blocked": 0, "replayed": 0,
    "selectedOwners": 1, "failedOwners": 0, "ownerRpcs": 1, "backlog": False,
    "metrics": {"operations": 25, "rowsRead": 99, "rowsWritten": 72, "complete": True}}
SKIPPED = {"ok": True, "skipped": True, "scanned": 0, "created": 0,
    "blocked": 0, "replayed": 0,
    "metrics": {"operations": 0, "rowsRead": 0, "rowsWritten": 0, "complete": True}}


class NoStorage(SimpleNamespace):
    def __getattr__(self, name):
        if name in {"DB", "storage", "ctx"} or name.startswith("NORULO_PREVIEW_"):
            raise AssertionError("Logging touched " + name)
        raise AttributeError(name)


@pytest.fixture
def console_capture(monkeypatch):
    events = []
    console = SimpleNamespace(**{level: (lambda message, level=level:
        events.append((level, json.loads(message)))) for level in ("log", "warn", "error")})
    monkeypatch.setitem(sys.modules, "js", SimpleNamespace(console=console))
    return events


def scheduled_worker(*, result=None, error=None):
    entry = load_entry()
    calls = []

    class Namespace:
        def idFromName(self, name):
            calls.append(("scope", name))
            return "fixed-local-scope"

        def get(self, identity):
            calls.append(("get", identity))

            async def runRecurring(*args, **kwargs):
                assert args == () and kwargs == {}
                calls.append(("rpc",))
                if error is not None:
                    raise error
                return result

            return SimpleNamespace(runRecurring=runRecurring)

    worker = entry.Default()
    worker.env = NoStorage(NORULO_MODE="production", NORULO_D1_ACCESS_ENABLED="1",
        NORULO_RECURRING_EXPENSES_ENABLED="1", RECURRING_SCHEDULER=Namespace())
    return worker, calls


def invoke(worker, *, scheduled=SCHEDULED, cron=PRODUCTION_RECURRING_CRON):
    return asyncio.run(worker.scheduled(SimpleNamespace(scheduledTime=scheduled,
        cron=cron), NoStorage(), NoStorage()))


def test_real_entry_healthy_receipt_preserves_single_rpc_no_storage_or_business_clock(console_capture):
    result = copy.deepcopy(HEALTHY)
    before = copy.deepcopy(result)
    worker, calls = scheduled_worker(result=result)
    assert invoke(worker, scheduled=SCHEDULED + 99_999_000) is None
    assert result == before
    assert calls == [("scope", RECURRING_SCHEDULER_SCOPE), ("get", "fixed-local-scope"), ("rpc",)]
    started, terminal = console_capture
    assert started == ("log", {"code": "NORULO_RECURRING_STARTED", "phase": "started",
        "status": "started", "healthy": False})
    assert terminal[0] == "log" and terminal[1]["code"] == "NORULO_RECURRING_COMPLETED"
    assert terminal[1]["status"] == "healthy" and terminal[1]["healthy"] is True
    assert terminal[1]["scheduledTime"] == SCHEDULED + 99_999_000
    assert terminal[1]["rowsWritten"] == 72 and terminal[1]["metricsComplete"] is True


@pytest.mark.parametrize("changes,status", [
    ({"failedOwners": 1}, "failed_owners"),
    ({"metrics": {"operations": 3, "rowsRead": 7, "rowsWritten": 1, "complete": False}}, "metrics_incomplete"),
    ({"metrics": None}, "metrics_incomplete"),
    ({"failedOwners": None}, "invalid_result"),
    ({"backlog": "private@example.test"}, "invalid_result"),
    ({"created": True}, "invalid_result"),
    ({"skipped": "private-provider-body"}, "invalid_result"),
])
def test_partial_or_malformed_success_never_becomes_healthy_or_changes_return(
        console_capture, changes, status):
    result = {**copy.deepcopy(HEALTHY), **changes}
    worker, calls = scheduled_worker(result=result)
    assert invoke(worker) is None  # Original strict ok guard still accepts True.
    assert len(calls) == 3
    assert len(console_capture) == 2
    level, terminal = console_capture[-1]
    assert level == "error" and terminal["code"] == "NORULO_RECURRING_FAILED"
    assert terminal["status"] == status and terminal["healthy"] is False


def test_backlog_and_blocked_are_separate_fixed_warnings(console_capture):
    worker, _ = scheduled_worker(result={**HEALTHY, "backlog": True, "blocked": 2})
    assert invoke(worker) is None
    assert [payload["code"] for _, payload in console_capture] == [
        "NORULO_RECURRING_STARTED", "NORULO_RECURRING_COMPLETED",
        "NORULO_RECURRING_BACKLOG", "NORULO_RECURRING_BLOCKED"]
    assert all(level == "warn" and payload["healthy"] is False
        for level, payload in console_capture[1:])


def test_skipped_root_receipt_is_completed_without_claiming_healthy_work(console_capture):
    worker, _ = scheduled_worker(result=SKIPPED)
    assert invoke(worker) is None
    terminal = console_capture[-1][1]
    assert terminal["code"] == "NORULO_RECURRING_COMPLETED"
    assert terminal["status"] == "skipped" and terminal["healthy"] is False
    assert "failedOwners" not in terminal and "backlog" not in terminal


@pytest.mark.parametrize("change", [{"created": 1}, {"backlog": 0}, {"failedOwners": 3},
    {"selectedOwners": 1}, {"metrics": {"complete": True}}])
def test_forged_skipped_shape_cannot_hide_failure_or_activity(change):
    terminal = recurring_log_receipts("returned", result={**SKIPPED, **change})[0][1]
    assert terminal["code"] == "NORULO_RECURRING_FAILED" and terminal["healthy"] is False


@pytest.mark.parametrize("code,status", [("RECURRING_BUSY", "busy"), ("RECURRING_DISABLED", "disabled")])
def test_early_root_failure_has_one_not_completed_terminal_and_original_exception(
        console_capture, code, status):
    worker, calls = scheduled_worker(result={"ok": False, "error": code})
    with pytest.raises(RuntimeError, match="^RECURRING_EXECUTION_UNAVAILABLE$"):
        invoke(worker)
    assert len(calls) == 3 and len(console_capture) == 2
    assert console_capture[-1][0] == "error"
    assert console_capture[-1][1]["code"] == "NORULO_RECURRING_NOT_COMPLETED"
    assert console_capture[-1][1]["status"] == status
    assert console_capture[-1][1]["healthy"] is False


@pytest.mark.parametrize("result", [{"ok": False, "error": "secret-provider-body"},
    {"ok": "true"}, {"ok": 1}, {}])
def test_rejected_result_logs_once_without_changing_original_guard(console_capture, result):
    worker, _ = scheduled_worker(result=result)
    with pytest.raises(RuntimeError, match="^RECURRING_EXECUTION_UNAVAILABLE$"):
        invoke(worker)
    assert len(console_capture) == 2
    assert console_capture[-1][1]["code"] == "NORULO_RECURRING_FAILED"
    assert "secret-provider-body" not in json.dumps(console_capture)


@pytest.mark.parametrize("error", [RuntimeError("secret-provider-body"), asyncio.CancelledError("secret-code")])
def test_rpc_exception_and_cancellation_rethrow_the_same_object(console_capture, error):
    worker, calls = scheduled_worker(error=error)
    async def observe_at_scheduled_boundary():
        with pytest.raises(type(error)) as raised:
            await worker.scheduled(SimpleNamespace(scheduledTime=SCHEDULED,
                cron=PRODUCTION_RECURRING_CRON), NoStorage(), NoStorage())
        assert raised.value is error
    # asyncio.run may recreate cancellation when retrieving a cancelled Task;
    # the scheduled coroutine itself must preserve the original exception.
    asyncio.run(observe_at_scheduled_boundary())
    assert len(calls) == 3
    assert len(console_capture) == 2
    assert console_capture[-1][0] == "error"
    assert console_capture[-1][1]["code"] == (
        "NORULO_RECURRING_CANCELLED" if isinstance(error, asyncio.CancelledError)
        else "NORULO_RECURRING_FAILED")
    assert "secret-" not in json.dumps(console_capture)


def test_disabled_top_level_never_touches_controller_namespace_or_emits(console_capture):
    worker, _ = scheduled_worker()
    worker.env = NoStorage(NORULO_MODE="production", NORULO_D1_ACCESS_ENABLED="0")
    assert asyncio.run(worker.scheduled(NoStorage(), NoStorage(), NoStorage())) is None
    assert console_capture == []


@pytest.mark.parametrize("value", [True, -1, 0.5, float("nan"), float("inf"),
    9007199254740992, 10**500, "secret-cookie", {"owner": "private"}])
def test_unsafe_numeric_payloads_are_suppressed_without_fabricating_zero(value):
    terminal = recurring_log_receipts("returned", result={**HEALTHY, "created": value},
        scheduled_time=value)[0][1]
    assert terminal["code"] == "NORULO_RECURRING_FAILED"
    assert "created" not in terminal and "scheduledTime" not in terminal
    assert "private" not in json.dumps(terminal) and "secret-cookie" not in json.dumps(terminal)


def test_receipt_sanitization_omits_unknown_nested_result_data_and_keeps_integral_ffi_numbers():
    result = SimpleNamespace(**{**HEALTHY, "checkpoint": {"pending": ["private-owner"]},
        "email": "private@example.test", "tokens": ["secret-token"], "created": 3.0})
    terminal = recurring_log_receipts("returned", result=result, scheduled_time=float(SCHEDULED))[0][1]
    assert terminal["healthy"] is True and type(terminal["created"]) is int
    assert not any(value in json.dumps(terminal) for value in ("private-owner", "private@example", "secret-token"))


def test_malicious_getter_does_not_escape_or_serialize_raw_failure():
    class Malicious:
        def __getattr__(self, name):
            raise ValueError("secret-provider-body")

    terminal = recurring_log_receipts("returned", result=Malicious())[0][1]
    assert terminal["code"] == "NORULO_RECURRING_FAILED"
    assert terminal["status"] == "invalid_result"
    assert "secret-provider-body" not in json.dumps(terminal)


def test_console_and_fallback_failures_cannot_change_rpc_success_or_cancellation(monkeypatch):
    def broken(*args):
        raise RuntimeError("sensitive-sink-error")

    monkeypatch.setitem(sys.modules, "js", SimpleNamespace(console=SimpleNamespace(
        log=broken, warn=broken, error=broken)))
    monkeypatch.setattr("builtins.print", broken)
    worker, _ = scheduled_worker(result=HEALTHY)
    assert invoke(worker) is None
    error = asyncio.CancelledError("private-cancellation")
    worker, _ = scheduled_worker(error=error)
    async def observe_at_scheduled_boundary():
        with pytest.raises(asyncio.CancelledError) as raised:
            await worker.scheduled(SimpleNamespace(scheduledTime=SCHEDULED,
                cron=PRODUCTION_RECURRING_CRON), NoStorage(), NoStorage())
        assert raised.value is error
    asyncio.run(observe_at_scheduled_boundary())


def test_cpython_fallback_emits_only_safe_fixed_json(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "js", SimpleNamespace())
    log_recurring_receipt("cancelled", scheduled_time=SCHEDULED)
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"code": "NORULO_RECURRING_CANCELLED", "phase": "cancelled",
        "status": "cancelled", "healthy": False, "scheduledTime": SCHEDULED}

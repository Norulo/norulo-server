"""Local protocol simulations; never model-quality or real provider evidence."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import ssl
from urllib.error import HTTPError

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("jev_quality_runner", ROOT / "scripts/check-jev-quality-local.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def mock_response(case):
    row = case["row"]
    choices = {"category": row["expectedCategoryId"] or "uncertain",
        "target": row["expectedTargetKind"] or "uncertain"}
    answers = {}
    for key, question in case["request"]["questions"].items():
        options, choice = tuple(question["criteria"]), choices[key]
        probabilities = {option: (0.97 if option == choice else 0.03 / (len(options) - 1))
            for option in options}
        answers[key] = {"type": "choice", "choice": choice,
            "probabilities": probabilities, "confidence": 0.95}
    return json.dumps({"model": runner.DEFAULT_JEV_MODEL, "answers": answers,
        "usage": {"input_tokens": 800, "output_tokens": 40}}).encode()


class LocalTransport:
    def __init__(self, *, fail_at=None, failure=None):
        self.calls = []
        self.cases = {case["requestHash"]: case for case in runner.load_suite()}
        self.fail_at, self.failure = fail_at, failure

    def __call__(self, payload):
        self.calls.append(payload)
        if len(self.calls) == self.fail_at:
            raise self.failure
        request_hash = runner.sha256(json.dumps(payload, ensure_ascii=False,
            separators=(",", ":")).encode())
        return mock_response(self.cases[request_hash])


def test_suite_has_exact_ids_and_reverses_actual_criteria_once():
    cases = runner.load_suite()
    assert len(cases) == 36
    assert tuple(case["row"]["id"] for case in cases) == runner.REQUIRED_IDS
    assert sum(case["row"]["language"] == "zh" for case in cases) == 18
    indexed = {case["row"]["id"]: case for case in cases}
    for case in cases:
        assert set(case["request"]["state"]) == {"purpose", "note"}
        assert "expected" not in json.dumps(case["request"])
        if "variantOf" in case["row"]:
            base = indexed[case["row"]["variantOf"]]
            assert all(order == list(reversed(base["criteriaOrder"][key]))
                for key, order in case["criteriaOrder"].items())


def test_default_prepares_budget_without_credentials_network_or_database(tmp_path, monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setattr(runner, "ProviderHTTP", lambda _: pytest.fail("preparation contacted provider"))
    directory = tmp_path / "quality"
    summary = runner.execute_run(directory)
    assert summary["providerAttempts"] == 0 and summary["allocatedMicrousd"] == 99108
    assert summary["remoteD1Operations"] == summary["remoteApplicationRequests"] == 0
    assert not summary["nativeWorkerProviderFetch"]
    events = [json.loads(line) for line in (directory / "attempts.jsonl").read_text().splitlines()]
    assert len(events) == 1 and events[0]["kind"] == "session"
    assert len(events[0]["cases"]) == 36


def test_missing_network_secret_makes_zero_attempts(tmp_path, monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    directory = tmp_path / "quality"
    with pytest.raises(runner.QualityError, match="QUALITY_SECRET_NOT_CONFIGURED"):
        runner.execute_run(directory, execute=True)
    assert len((directory / "attempts.jsonl").read_text().splitlines()) == 1


def test_successful_simulation_is_capped_persistent_and_never_quality_evidence(tmp_path):
    directory, transport = tmp_path / "quality", LocalTransport()
    summary = runner.execute_run(directory, execute=True, transport=transport)
    assert len(transport.calls) == summary["providerAttempts"] == 36
    assert summary["attemptReservedMicrousd"] == 99108
    assert summary["realProviderRequests"] == 0
    assert summary["quality"]["providerEvidenceComplete"] is False
    assert summary["quality"]["eligibleForReview"] is False
    rows = [json.loads(line) for line in (directory / "results.jsonl").read_text().splitlines()]
    assert all(not row["realProvider"] for row in rows)
    assert all(row["reservationMicrousd"] == 2753 for row in rows)
    second = runner.execute_run(directory, resume=True, execute=True, transport=transport)
    assert second == summary and len(transport.calls) == 36
    assert len((directory / "attempts.jsonl").read_text().splitlines()) == 73
    with pytest.raises(runner.QualityError, match="QUALITY_RUN_EXISTS_USE_RESUME"):
        runner.execute_run(directory, execute=True, transport=transport)
    assert len(transport.calls) == 36


@pytest.mark.parametrize("failure", [
    runner.ProviderFailure("transport_unknown"), runner.ProviderFailure("http_rejection", 429),
    OSError("synthetic private key diagnostic"),
])
def test_failure_stops_without_retry_refund_or_restart_dispatch(tmp_path, failure, capsys):
    directory = tmp_path / "quality"
    transport = LocalTransport(fail_at=3, failure=failure)
    with pytest.raises(runner.QualityError, match="QUALITY_PROVIDER_FAILURE_STOPPED"):
        runner.execute_run(directory, execute=True, transport=transport)
    assert len(transport.calls) == 3
    summary = json.loads((directory / "summary.json").read_text())
    assert summary["allocatedMicrousd"] == 99108 and summary["attemptReservedMicrousd"] == 8259
    with pytest.raises(runner.QualityError, match="QUALITY_PROVIDER_FAILURE_STOPPED"):
        runner.execute_run(directory, resume=True, execute=True, transport=transport)
    assert len(transport.calls) == 3
    assert "private key" not in (directory / "attempts.jsonl").read_text()
    assert capsys.readouterr().out == ""


def test_interrupted_request_remains_unknown_and_can_never_resume(tmp_path):
    directory = tmp_path / "quality"
    transport = LocalTransport(fail_at=1, failure=KeyboardInterrupt())
    with pytest.raises(KeyboardInterrupt):
        runner.execute_run(directory, execute=True, transport=transport)
    events = [json.loads(line) for line in (directory / "attempts.jsonl").read_text().splitlines()]
    assert len(events) == 2 and events[-1]["kind"] == "reserved"
    with pytest.raises(runner.QualityError, match="QUALITY_OUTCOME_UNKNOWN_STOPPED"):
        runner.execute_run(directory, resume=True, execute=True, transport=transport)
    assert len(transport.calls) == 1


def test_reservation_fsync_failure_prevents_provider_dispatch(tmp_path, monkeypatch):
    original_append = runner._append
    def failed_append(path, event):
        if event["kind"] == "reserved":
            raise OSError("synthetic fsync failure")
        original_append(path, event)
    monkeypatch.setattr(runner, "_append", failed_append)
    transport = LocalTransport()
    with pytest.raises(OSError):
        runner.execute_run(tmp_path / "quality", execute=True, transport=transport)
    assert not transport.calls


def test_completion_fsync_failure_stops_and_preserves_unknown_attempt(tmp_path, monkeypatch):
    directory, transport = tmp_path / "quality", LocalTransport()
    original_append = runner._append
    def failed_append(path, event):
        if event["kind"] == "completed":
            raise OSError("synthetic completion fsync failure")
        original_append(path, event)
    monkeypatch.setattr(runner, "_append", failed_append)
    with pytest.raises(OSError):
        runner.execute_run(directory, execute=True, transport=transport)
    monkeypatch.setattr(runner, "_append", original_append)
    with pytest.raises(runner.QualityError, match="QUALITY_OUTCOME_UNKNOWN_STOPPED"):
        runner.execute_run(directory, resume=True, execute=True, transport=transport)
    assert len(transport.calls) == 1


def test_resume_skips_completed_cases_even_after_artifact_loss(tmp_path):
    directory, transport = tmp_path / "quality", LocalTransport()
    summary = runner.execute_run(directory, execute=True, transport=transport)
    (directory / "results.jsonl").unlink()
    (directory / "summary.json").unlink()
    (directory / "results.jsonl.tmp").write_text("interrupted generated artifact")
    assert runner.execute_run(directory, resume=True, execute=True, transport=transport) == summary
    assert len(transport.calls) == 36
    assert len((directory / "results.jsonl").read_text().splitlines()) == 36


def test_journal_contract_change_or_partial_line_blocks_requests(tmp_path):
    directory, transport = tmp_path / "quality", LocalTransport()
    runner.execute_run(directory, execute=True, transport=transport)
    journal = directory / "attempts.jsonl"
    raw = journal.read_bytes()
    journal.write_bytes(raw[:-1])
    with pytest.raises(runner.QualityError, match="QUALITY_JOURNAL_INVALID"):
        runner.execute_run(directory, resume=True, execute=True, transport=transport)
    events = [json.loads(line) for line in raw.splitlines()]
    events[0]["fixtureSha256"] = "changed"
    journal.write_bytes(b"".join(runner.canonical_bytes(event) + b"\n" for event in events))
    with pytest.raises(runner.QualityError, match="QUALITY_JOURNAL_CONTRACT_MISMATCH"):
        runner.execute_run(directory, resume=True, execute=True, transport=transport)
    assert len(transport.calls) == 36


def test_modified_prediction_cannot_survive_resume_validation(tmp_path):
    directory, transport = tmp_path / "quality", LocalTransport()
    runner.execute_run(directory, execute=True, transport=transport)
    journal = directory / "attempts.jsonl"
    events = [json.loads(line) for line in journal.read_text().splitlines()]
    events[2]["result"]["predictedCategoryId"] = "invented"
    journal.write_bytes(b"".join(runner.canonical_bytes(event) + b"\n" for event in events))
    with pytest.raises(runner.QualityError, match="QUALITY_JOURNAL_INVALID"):
        runner.execute_run(directory, resume=True, execute=True, transport=transport)
    assert len(transport.calls) == 36


def test_exclusive_lock_blocks_competing_runner_without_dispatch(tmp_path):
    directory = tmp_path / "quality"
    runner.execute_run(directory)
    with runner.run_lock(directory, resume=True):
        with pytest.raises(runner.QualityError, match="QUALITY_RUN_BUSY"):
            runner.execute_run(directory, resume=True, execute=True)


@pytest.mark.parametrize("usage", [
    {"input_tokens": None, "output_tokens": 40}, {"input_tokens": 800, "output_tokens": None},
    {"input_tokens": 65537, "output_tokens": 40}, {"input_tokens": True, "output_tokens": 40},
])
def test_missing_or_out_of_bound_usage_stops_before_next_call(tmp_path, usage):
    calls = []
    def bad_usage(payload):
        calls.append(payload)
        response = json.loads(mock_response(runner.load_suite()[0]))
        response["usage"] = usage
        return json.dumps(response).encode()
    with pytest.raises(runner.QualityError, match="QUALITY_PROVIDER_FAILURE_STOPPED"):
        runner.execute_run(tmp_path / "quality", execute=True, transport=bad_usage)
    assert len(calls) == 1


def test_http_uses_fixed_url_inherited_proxy_verified_tls_and_one_post(monkeypatch):
    calls, handlers = [], []
    class Response:
        headers = {}
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self, limit):
            assert limit == runner.MAX_RESPONSE_BYTES + 1
            return b"response-bytes"
    class Opener:
        def open(self, request, timeout):
            calls.append((request, timeout))
            return Response()
    def build(*args):
        handlers.extend(args)
        return Opener()
    monkeypatch.setattr(runner, "build_opener", build)
    transport = runner.ProviderHTTP("synthetic-secret")
    assert transport({"synthetic": "payload"}) == b"response-bytes"
    request, timeout = calls[0]
    assert len(calls) == 1 and request.full_url == "https://api.typesafe.ai/v1/systemone"
    assert request.get_method() == "POST" and timeout == 3
    assert request.get_header("Authorization") == "Bearer synthetic-secret"
    context = next(handler._context for handler in handlers if isinstance(handler, runner.HTTPSHandler))
    assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname is True
    assert not any(isinstance(handler, runner.NoRedirect) and
        handler.redirect_request(None, None, 302, "", {}, "https://hostile.invalid") is not None
        for handler in handlers)


def test_http_rejection_does_not_follow_redirect_read_error_body_or_retry(monkeypatch):
    calls = []
    class PrivateBody(io.BytesIO):
        def read(self, *args):
            pytest.fail("provider rejection body read")
    class Opener:
        def open(self, request, timeout):
            calls.append(request)
            raise HTTPError(request.full_url, 302, "private secret diagnostic", {}, PrivateBody(b"secret"))
    monkeypatch.setattr(runner, "build_opener", lambda *args: Opener())
    with pytest.raises(runner.ProviderFailure) as caught:
        runner.ProviderHTTP("synthetic-secret")({})
    assert caught.value.outcome == "http_rejection" and caught.value.status == 302
    assert len(calls) == 1 and "secret" not in str(caught.value)


def test_total_deadline_is_removed_after_transport_error():
    with pytest.raises(OSError):
        with runner.total_deadline():
            raise OSError("synthetic failure")
    assert runner.signal.getitimer(runner.signal.ITIMER_REAL)[0] == 0

#!/usr/bin/env python3
"""Bounded real-provider quality capture, with only local files and no D1.

Default prepares a reviewed 36-case journal without network requests. --execute
uses the inherited HTTPS proxy/CA and TYPESAFE_API_KEY network Secret. --resume
skips durably completed cases but refuses any failed or uncertain attempt. This
CPython HTTPS transport is separate from native Worker fetch/FFI acceptance.
No application endpoint, Cloudflare account API or database is contacted.
Use one reviewed run directory for the authorized 36-attempt run; do not start
another directory to retry failures. The journal is authoritative, every reserved
attempt may have been billed, and a summary can be stale after interruption.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import runpy
import signal
import ssl
import sys
import time
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from norulo_server.cloudflare_jev_gateway import JEV_URL, MAX_RESPONSE_BYTES, REQUEST_TIMEOUT_MS
from norulo_server.cloudflare_ledger_suggestions import (
    CONFIDENCE_THRESHOLD, QUESTION_VERSION, suggestion_questions,
)
from norulo_server.ledger_plan_policy import JEV_RESERVATION_MICROUSD
from norulo_server.typesafe_client import DEFAULT_JEV_MODEL, build_request, validate_response

FIXTURE = ROOT / "tests/fixtures/jev-ledger-synthetic-v2.jsonl"
FIXTURE_SHA256 = "a8154f94fe24b1388dddca60febef7e864b70dfb42be68cc4fbab7001b242add"
ATTEMPT_CAP = 36
RESERVATION_CAP_MICROUSD = 99_108
JOURNAL_BYTE_CAP = 512 * 1024
REQUIRED_IDS = tuple([f"en{index:02d}" for index in range(1, 16)]
    + [f"zh{index:02d}" for index in range(1, 16)]
    + [f"{language}{index:02d}-reversed" for language in ("en", "zh") for index in (1, 3, 9)])


class QualityError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class ProviderFailure(Exception):
    def __init__(self, outcome, status=None):
        self.outcome, self.status = outcome, status
        super().__init__(outcome)


def canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
        separators=(",", ":"), sort_keys=True).encode("utf-8")


def sha256(value):
    return hashlib.sha256(value).hexdigest()


def load_suite():
    raw = FIXTURE.read_bytes()
    if (sha256(raw) != FIXTURE_SHA256 or DEFAULT_JEV_MODEL != "jev-1.13.0"
            or QUESTION_VERSION != "ledger-suggest-v2" or JEV_RESERVATION_MICROUSD != 2753
            or JEV_RESERVATION_MICROUSD * ATTEMPT_CAP != RESERVATION_CAP_MICROUSD
            or JEV_URL != "https://api.typesafe.ai/v1/systemone"):
        raise QualityError("QUALITY_CONTRACT_CHANGED")
    rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    if tuple(row.get("id") for row in rows) != REQUIRED_IDS:
        raise QualityError("QUALITY_FIXTURE_IDS_CHANGED")
    indexed = {row["id"]: row for row in rows}
    cases = []
    for row in rows:
        if (row.get("provenance") != "agent-authored-synthetic"
                or "predictedCategoryId" in row or "predictedTargetKind" in row):
            raise QualityError("QUALITY_FIXTURE_INVALID")
        base = indexed.get(row.get("variantOf"))
        questions = suggestion_questions((base or row)["categories"])
        if row.get("reverseCriteria") is True:
            if base is None:
                raise QualityError("QUALITY_ORDER_VARIANT_INVALID")
            # Variant categories are already reversed in the fixture. Generate
            # from the base to avoid reversing them twice; every option,
            # including uncertain, must exactly reverse the base request.
            for question in questions.values():
                question["criteria"] = dict(reversed(tuple(question["criteria"].items())))
        payload = build_request(state={"purpose": row["purpose"], "note": row["note"]},
            questions=questions, model=DEFAULT_JEV_MODEL)
        case = {"row": row, "request": payload,
            "requestHash": sha256(json.dumps(payload, ensure_ascii=False, allow_nan=False,
                separators=(",", ":")).encode("utf-8")),
            "criteriaOrder": {key: list(question["criteria"]) for key, question in payload["questions"].items()}}
        if base:
            base_case = next(item for item in cases if item["row"]["id"] == base["id"])
            if any(order != list(reversed(base_case["criteriaOrder"][key]))
                   for key, order in case["criteriaOrder"].items()):
                raise QualityError("QUALITY_ORDER_VARIANT_INVALID")
            case["baseRequestHash"] = base_case["requestHash"]
        cases.append(case)
    return cases


def session_manifest(cases, directory, *, simulated=False):
    files = ("norulo_server/cloudflare_jev_gateway.py", "norulo_server/typesafe_client.py",
        "norulo_server/cloudflare_ledger_suggestions.py", "norulo_server/ledger_plan_policy.py",
        "scripts/evaluate-ledger-suggestions.py", "scripts/check-jev-quality-local.py")
    return {"kind": "session", "version": 1, "fixtureSha256": FIXTURE_SHA256,
        "runId": sha256(str(directory.resolve()).encode("utf-8"))[:32],
        "modelVersion": DEFAULT_JEV_MODEL, "questionVersion": QUESTION_VERSION,
        "attemptCap": ATTEMPT_CAP, "allocatedMicrousd": RESERVATION_CAP_MICROUSD,
        "attemptReservationMicrousd": JEV_RESERVATION_MICROUSD,
        "endpoint": JEV_URL, "remoteD1Operations": 0, "remoteApplicationRequests": 0,
        "transport": "injected-local-test-transport" if simulated else "cpython-https-via-environment-proxy",
        "realProvider": not simulated, "nativeWorkerProviderFetch": False,
        "sourceSha256": {name: sha256((ROOT / name).read_bytes()) for name in files},
        "cases": [{"id": item["row"]["id"], "requestHash": item["requestHash"],
            "criteriaOrder": item["criteriaOrder"],
            **({"baseRequestHash": item["baseRequestHash"]} if "baseRequestHash" in item else {})}
            for item in cases]}


def _sync_directory(directory):
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _append(path, event):
    descriptor = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "ab", closefd=False) as handle:
            handle.write(canonical_bytes(event) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)
    _sync_directory(path.parent)


def _write_artifact(path, raw):
    temporary = path.with_suffix(path.suffix + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)
    os.replace(temporary, path)
    _sync_directory(path.parent)


@contextlib.contextmanager
def run_lock(directory, *, resume):
    directory = directory.resolve()
    if not any(directory.is_relative_to(root) for root in (Path("/workspace"), Path("/tmp"))):
        raise QualityError("QUALITY_RUN_DIRECTORY_INVALID")
    if resume:
        if not directory.is_dir():
            raise QualityError("QUALITY_RUN_NOT_FOUND")
    else:
        try:
            directory.mkdir(parents=True, exist_ok=False, mode=0o700)
        except FileExistsError:
            raise QualityError("QUALITY_RUN_EXISTS_USE_RESUME") from None
    descriptor = os.open(directory / "run.lock", os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise QualityError("QUALITY_RUN_BUSY") from None
        yield directory
    finally:
        os.close(descriptor)


def read_journal(path, manifest, cases):
    if path.is_symlink():
        raise QualityError("QUALITY_JOURNAL_INVALID")
    raw = path.read_bytes()
    if len(raw) > JOURNAL_BYTE_CAP or not raw.endswith(b"\n"):
        raise QualityError("QUALITY_JOURNAL_INVALID")
    try:
        events = [json.loads(line) for line in raw.splitlines()]
    except (ValueError, UnicodeError):
        raise QualityError("QUALITY_JOURNAL_INVALID") from None
    if not events or events[0] != manifest:
        raise QualityError("QUALITY_JOURNAL_CONTRACT_MISMATCH")
    reserved, results = [], []
    for event in events[1:]:
        if not isinstance(event, dict):
            raise QualityError("QUALITY_JOURNAL_INVALID")
        if event.get("kind") == "reserved":
            if (len(reserved) != len(results) or len(reserved) >= ATTEMPT_CAP
                    or event != {"kind": "reserved", "id": manifest["cases"][len(reserved)]["id"],
                        "requestHash": manifest["cases"][len(reserved)]["requestHash"],
                        "reservationMicrousd": JEV_RESERVATION_MICROUSD}):
                raise QualityError("QUALITY_JOURNAL_INVALID")
            reserved.append(event)
        elif event.get("kind") == "completed":
            if len(reserved) != len(results) + 1 or event.get("id") != reserved[-1]["id"]:
                raise QualityError("QUALITY_JOURNAL_INVALID")
            result = event.get("result")
            if not isinstance(result, dict) or result.get("id") != event["id"]:
                raise QualityError("QUALITY_JOURNAL_INVALID")
            successful_outcome = "valid_response" if manifest["realProvider"] else "simulated_response"
            if result.get("providerOutcome") == successful_outcome:
                try:
                    case = cases[len(results)]
                    answer = validate_quality_response(canonical_bytes({"model": result["modelVersion"],
                        "answers": result["answers"], "usage": {
                            "input_tokens": result["usage"]["inputTokens"],
                            "output_tokens": result["usage"]["outputTokens"]}}), case)
                    if (type(result["latencyMs"]) is not int or result["latencyMs"] < 0
                            or normalized_result(case, answer, latency_ms=result["latencyMs"],
                                outcome="valid_response", manifest=manifest) != result):
                        raise ValueError()
                except (KeyError, ValueError, TypeError):
                    raise QualityError("QUALITY_JOURNAL_INVALID") from None
            results.append(result)
        else:
            raise QualityError("QUALITY_JOURNAL_INVALID")
    if len(reserved) != len(results):
        raise QualityError("QUALITY_OUTCOME_UNKNOWN_STOPPED")
    successful_outcome = "valid_response" if manifest["realProvider"] else "simulated_response"
    if any(row.get("providerOutcome") != successful_outcome for row in results):
        raise QualityError("QUALITY_PROVIDER_FAILURE_STOPPED")
    return results


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, newurl):
        return None


@contextlib.contextmanager
def total_deadline():
    if not hasattr(signal, "setitimer") or signal.getitimer(signal.ITIMER_REAL)[0] != 0:
        raise QualityError("QUALITY_TOTAL_DEADLINE_UNAVAILABLE")
    previous = signal.getsignal(signal.SIGALRM)
    def expired(signum, frame):
        raise TimeoutError("QUALITY_PROVIDER_DEADLINE")
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, REQUEST_TIMEOUT_MS / 1000)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


class ProviderHTTP:
    """Single fixed HTTPS POST; default ProxyHandler/CA trust stay inherited."""
    def __init__(self, secret):
        self.secret = secret
        self.opener = build_opener(NoRedirect(), HTTPSHandler(context=ssl.create_default_context()))

    def __call__(self, payload):
        request = Request(JEV_URL, method="POST", headers={
            "Authorization": "Bearer " + self.secret, "Content-Type": "application/json"},
            data=json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8"))
        try:
            with total_deadline(), self.opener.open(request, timeout=REQUEST_TIMEOUT_MS / 1000) as response:
                length = response.headers.get("content-length")
                if length and (not str(length).isascii() or not str(length).isdecimal()
                               or int(length) > MAX_RESPONSE_BYTES):
                    raise ProviderFailure("invalid_response")
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise ProviderFailure("invalid_response")
                return raw
        except HTTPError as error:
            # Do not read, store or print a provider's rejection body.
            error.close()
            raise ProviderFailure("http_rejection", int(error.code)) from None
        except ProviderFailure:
            raise
        except Exception:
            raise ProviderFailure("transport_unknown") from None


def validate_quality_response(raw, case):
    answer = validate_response(raw, requested_model=DEFAULT_JEV_MODEL,
        expected_questions={key: tuple(question["criteria"])
            for key, question in case["request"]["questions"].items()})
    if (any(type(value) is not int for value in answer["usage"].values())
            or answer["usage"]["inputTokens"] > 65536):
        raise ValueError("QUALITY_USAGE_OUT_OF_BOUND")
    return answer


def normalized_result(case, answer, *, latency_ms, outcome, manifest, http_status=None):
    row = case["row"]
    predictions = {}
    for question, field in (("category", "predictedCategoryId"), ("target", "predictedTargetKind")):
        choice = answer["answers"][question] if answer else None
        predictions[field] = (choice["choice"] if choice and choice["choice"] != "uncertain"
            and choice["confidence"] >= CONFIDENCE_THRESHOLD else None)
    return {"id": row["id"], "language": row["language"], "runId": manifest["runId"],
        "provenance": "agent-authored-synthetic",
        "expectedCategoryId": row["expectedCategoryId"], "expectedTargetKind": row["expectedTargetKind"],
        **predictions, **({"variantOf": row["variantOf"]} if "variantOf" in row else {}),
        "requestHash": case["requestHash"], "criteriaOrder": case["criteriaOrder"],
        "reservationMicrousd": JEV_RESERVATION_MICROUSD,
        "transport": manifest["transport"], "realProvider": manifest["realProvider"],
        "modelVersion": answer["model"] if answer else None,
        "questionVersion": QUESTION_VERSION,
        "providerOutcome": "simulated_response" if outcome == "valid_response" and not manifest["realProvider"] else outcome,
        "latencyMs": latency_ms, "usage": answer["usage"] if answer else None,
        "answers": answer["answers"] if answer else None,
        **({"httpStatus": http_status} if http_status is not None else {})}


def publish_results(directory, results, *, complete, manifest):
    raw = b"".join(canonical_bytes(row) + b"\n" for row in results)
    # Stale temp files can only result from interrupted local artifact writes;
    # remove those exact generated files. The journal remains the authority.
    for name in ("results.jsonl.tmp", "summary.json.tmp"):
        path = directory / name
        if path.is_file() and not path.is_symlink():
            path.unlink()
    _write_artifact(directory / "results.jsonl", raw)
    usages = [row["usage"]["inputTokens"] for row in results if row.get("usage")]
    numeric_usage = len(usages) == len(results) and all(type(value) is int for value in usages)
    summary = {"complete": complete, "providerAttempts": len(results),
        "attemptCap": ATTEMPT_CAP, "allocatedMicrousd": RESERVATION_CAP_MICROUSD,
        "attemptReservedMicrousd": len(results) * JEV_RESERVATION_MICROUSD,
        "validResponses": sum(row["providerOutcome"] == "valid_response" for row in results),
        "inputTokens": sum(usages) if numeric_usage else None,
        "usageDerivedCostUsd": sum(usages) * 0.042 / 1_000_000 if numeric_usage else None,
        "remoteD1Operations": 0, "remoteApplicationRequests": 0,
        "transport": manifest["transport"], "nativeWorkerProviderFetch": False,
        "realProviderRequests": len(results) if manifest["realProvider"] else 0,
        "automaticRetries": 0, "usageEstimateIsInvoice": False}
    if complete:
        evaluate = runpy.run_path(str(ROOT / "scripts/evaluate-ledger-suggestions.py"))["evaluate"]
        summary["quality"] = evaluate(results)
        if not manifest["realProvider"]:
            summary["quality"].update(providerEvidenceComplete=False, eligibleForReview=False)
    _write_artifact(directory / "summary.json", canonical_bytes(summary) + b"\n")
    return summary


def execute_run(directory, *, resume=False, execute=False, transport=None, clock=time.monotonic):
    cases = load_suite()
    manifest = session_manifest(cases, directory, simulated=transport is not None)
    with run_lock(directory, resume=resume) as directory:
        journal = directory / "attempts.jsonl"
        if resume:
            results = read_journal(journal, manifest, cases)
        else:
            _append(journal, manifest)
            results = []
        if not execute:
            return publish_results(directory, results, complete=len(results) == ATTEMPT_CAP, manifest=manifest)
        if len(results) == ATTEMPT_CAP:
            return publish_results(directory, results, complete=True, manifest=manifest)
        if transport is None:
            secret = os.environ.get("TYPESAFE_API_KEY", "").strip()
            if not secret:
                raise QualityError("QUALITY_SECRET_NOT_CONFIGURED")
            transport = ProviderHTTP(secret)
        for case in cases[len(results):]:
            _append(journal, {"kind": "reserved", "id": case["row"]["id"],
                "requestHash": case["requestHash"], "reservationMicrousd": JEV_RESERVATION_MICROUSD})
            started = clock()
            answer, outcome, status = None, "valid_response", None
            try:
                raw = transport(case["request"])
            except ProviderFailure as error:
                outcome, status = error.outcome, error.status
            except Exception:
                outcome = "transport_unknown"
            else:
                try:
                    answer = validate_quality_response(raw, case)
                except Exception:
                    outcome = "invalid_response"
            elapsed = max(0, round((clock() - started) * 1000))
            result = normalized_result(case, answer, latency_ms=elapsed, outcome=outcome,
                http_status=status, manifest=manifest)
            _append(journal, {"kind": "completed", "id": case["row"]["id"], "result": result})
            results.append(result)
            if outcome != "valid_response":
                publish_results(directory, results, complete=False, manifest=manifest)
                raise QualityError("QUALITY_PROVIDER_FAILURE_STOPPED")
        return publish_results(directory, results, complete=True, manifest=manifest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--execute", action="store_true", help="Make at most 36 real paid provider requests")
    parser.add_argument("--resume", action="store_true", help="Resume a matching journal; never repeat an unknown/completed attempt")
    args = parser.parse_args()
    try:
        summary = execute_run(args.run_dir, resume=args.resume, execute=args.execute)
    except QualityError as error:
        print(json.dumps({"error": error.code}), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print(json.dumps({"error": "QUALITY_OUTCOME_UNKNOWN_STOPPED"}), file=sys.stderr)
        return 130
    except Exception:
        # Never stringify an exception containing credentials, bodies or URLs.
        print(json.dumps({"error": "QUALITY_LOCAL_FAILURE"}), file=sys.stderr)
        return 1
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

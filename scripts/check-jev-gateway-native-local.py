#!/usr/bin/env python3
"""Native canonical Jev gateway with a loopback fake provider; no real key/D1.

This proves Worker Python/JS fetch, streaming and deadline behavior locally.
The provider endpoint is deliberately remapped inside the fixture. This is not
real-provider model quality or native production outbound-HTTPS acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from norulo_server.typesafe_client import validate_response

WORKER = ROOT / "cloudflare/server"
BUNDLE_SHA256 = "3c3fd5a4179230e21e018e28b0e735e7c4abd8fe8e4ff39d2fd6bb2ea3a2e260"
CASES = ("valid", "redirect", "oversized-header", "oversized-stream", "deadline")

ENTRY = r'''
import json
import sys
from types import SimpleNamespace
from workers import WorkerEntrypoint, Response
import js as original_js
from norulo_server.cloudflare_jev_gateway import WorkerJevGateway, JEV_URL
from norulo_server.typesafe_client import build_request, DEFAULT_JEV_MODEL, validate_response

current_case = ""
calls = []
FIXTURE_ORIGIN = "__FIXTURE_ORIGIN__"

class Bridge:
    def __getattr__(self, name):
        return getattr(original_js, name)
    async def fetch(self, url, options):
        assert str(url) == JEV_URL
        assert str(options.method) == "POST" and str(options.redirect) == "manual"
        assert str(options.headers.Authorization) == "Bearer synthetic-local-only-key"
        assert str(getattr(options.headers, "Content-Type")) == "application/json"
        payload = json.loads(str(options.body))
        assert payload["model"] == DEFAULT_JEV_MODEL
        calls.append({"case": current_case, "method": str(options.method),
            "redirect": str(options.redirect), "fixedUrlChecked": True,
            "syntheticAuthorizationChecked": True, "nativeAbortSignal": hasattr(options.signal, "aborted")})
        assert len(calls) <= 5
        return await original_js.fetch(FIXTURE_ORIGIN + "/" + current_case, options)

class Default(WorkerEntrypoint):
    async def fetch(self, request):
        global current_case
        assert str(request.method) == "POST"
        raw = await request.bytes()
        raw = raw if isinstance(raw, bytes) else raw.to_bytes()
        assert len(raw) <= 128
        data = json.loads(raw)
        assert set(data) == {"case"} and data["case"] in {
            "valid", "redirect", "oversized-header", "oversized-stream", "deadline"}
        current_case = data["case"]
        before = len(calls)
        gateway = WorkerJevGateway(SimpleNamespace(TYPESAFE_API_KEY="synthetic-local-only-key",
            NORULO_JEV_SUGGESTIONS_ENABLED="1", NORULO_JEV_SUGGESTIONS_EVALUATED="1"))
        payload = build_request(state={"purpose": "synthetic expense", "note": "local fixture only"},
            model=DEFAULT_JEV_MODEL, questions={"target": {"type": "choice",
                "instructions": "Classify the stated expense scope.", "criteria": {
                    "project": "Only one project", "shared": "Shared across projects",
                    "uncertain": "No scope specified"}}})
        outcome = "rejected"
        failure_code = None
        failure_type = None
        try:
            sys.modules["js"] = Bridge()
            result = await gateway.evaluate(payload)
            normalized = validate_response(result, requested_model=DEFAULT_JEV_MODEL,
                expected_questions={"target": tuple(payload["questions"]["target"]["criteria"])})
            assert normalized["answers"]["target"]["choice"] == "uncertain"
            outcome = "accepted"
        except Exception as error:
            failure_type = type(error).__name__
            # Only map a reviewed fixed local size error. Unknown provider or
            # runtime errors must never be stringified into logs/artifacts.
            if type(error) is ValueError and error.args == ("JEV_RESPONSE_TOO_LARGE",):
                failure_code = "JEV_RESPONSE_TOO_LARGE"
        finally:
            sys.modules["js"] = original_js
        assert len(calls) == before + 1
        return Response.json({"case": current_case, "outcome": outcome,
            "providerAttempts": len(calls) - before, "request": calls[-1],
            "failureCode": failure_code, "failureType": failure_type})
'''


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, newurl):
        return None


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(directory, port):
    directory = directory.resolve()
    if not directory.is_relative_to(Path("/workspace")) or not 1024 <= port <= 63535:
        raise ValueError("Use a fresh /workspace directory and an unprivileged local port")
    directory.mkdir(parents=True, exist_ok=False)
    valid_raw = json.dumps({"model": "jev-1.13.0", "answers": {"target": {
        "type": "choice", "choice": "uncertain", "confidence": 0.95,
        "probabilities": {"project": 0.015, "shared": 0.015, "uncertain": 0.97}}},
        "usage": {"input_tokens": 100, "output_tokens": 20}}).encode()
    oversized_raw = valid_raw + b" " * (65537 - len(valid_raw))
    assert len(oversized_raw) == 65537
    # Without the gateway's 64 KiB guard this is an acceptable provider body;
    # schema rejection cannot make the size tests pass accidentally.
    assert validate_response(oversized_raw, requested_model="jev-1.13.0",
        expected_questions={"target": ("project", "shared", "uncertain")})[
        "answers"]["target"]["choice"] == "uncertain"
    observed = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            length = int(self.headers.get("content-length", "0"))
            assert 0 < length <= 4096 and len(observed) < len(CASES)
            payload = json.loads(self.rfile.read(length))
            assert payload["model"] == "jev-1.13.0"
            assert self.headers.get("authorization") == "Bearer synthetic-local-only-key"
            case = self.path.removeprefix("/")
            assert case in CASES
            observed.append(case)
            if case == "redirect":
                self.send_response(302)
                self.send_header("Location", "https://unrequested.invalid")
                self.end_headers()
                return
            if case == "deadline":
                time.sleep(3.4)
            if case in {"oversized-header", "oversized-stream"}:
                raw = oversized_raw
            else:
                raw = valid_raw
            self.send_response(200)
            if case != "oversized-stream":
                self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            try:
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionResetError):
                pass
    provider = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    provider.daemon_threads = True
    threading.Thread(target=provider.serve_forever, daemon=True).start()
    source = directory / "src"
    source.mkdir()
    (source / "entry.py").write_text(ENTRY.replace("__FIXTURE_ORIGIN__",
        "http://127.0.0.1:" + str(provider.server_port)))
    shutil.copytree(ROOT / "norulo_server", source / "norulo_server",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copytree(WORKER / "python_modules", directory / "python_modules",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (directory / "node_modules").symlink_to(WORKER / "node_modules", target_is_directory=True)
    config = {"name": "norulo-jev-gateway-native-local-only", "main": "src/entry.py",
        "compatibility_date": "2026-09-23", "compatibility_flags": ["python_workers"],
        "workers_dev": False, "preview_urls": False, "routes": []}
    (directory / "wrangler.jsonc").write_text(json.dumps(config))
    bundle = Path("/workspace/.cache/norulo-pyodide/pyodide_314.0.6_2026-08-17_6.capnp.bin")
    if not bundle.is_file() or sha256(bundle) != BUNDLE_SHA256:
        raise ValueError("Pinned verified Workerd Python bundle missing")
    binary = WORKER / "node_modules/@cloudflare/workerd-linux-64/bin/workerd"
    wrapper = directory / "workerd-local-cache.sh"
    wrapper.write_text("#!/bin/sh\nexec " + shlex.quote(str(binary))
        + ' "$@" --pyodide-bundle-disk-cache-dir=/workspace/.cache/norulo-pyodide\n')
    wrapper.chmod(0o700)
    env = {**os.environ, "XDG_CACHE_HOME": "/workspace/.cache", "XDG_CONFIG_HOME": "/workspace/.config",
        "WRANGLER_SEND_METRICS": "false", "MINIFLARE_WORKERD_PATH": str(wrapper),
        "WRANGLER_LOG_PATH": str(directory / "wrangler-debug.log")}
    evidence = {"passed": False, "localOnly": True, "nativePythonFFI": True,
        "canonicalWorkerJevGateway": True, "endpointRemappedToLoopbackFakeProvider": True,
        "nativeRealProviderHttpsAccepted": False, "realProviderRequests": 0,
        "remoteD1Operations": 0, "remoteApplicationRequests": 0,
        "databaseBindings": [], "durableObjectBindings": [], "clientRetries": 0,
        "workerdSha256": sha256(binary), "pythonBundleSha256": BUNDLE_SHA256,
        "oversizedFixture": {"byteLength": len(oversized_raw), "validResponseWithoutGatewayCap": True},
        "sourceSha256": {name: sha256(ROOT / name) for name in (
            "norulo_server/cloudflare_jev_gateway.py", "norulo_server/typesafe_client.py")},
        "cases": []}
    process = None
    try:
        log_path = directory / "runtime.log"
        with log_path.open("w") as log:
            process = subprocess.Popen(["node", str(WORKER / "node_modules/wrangler/bin/wrangler.js"),
                "dev", "--local", "--config", str(directory / "wrangler.jsonc"),
                "--ip", "127.0.0.1", "--port", str(port), "--inspector-port", str(port + 1000),
                "--persist-to", str(directory / "state")], cwd=directory, env=env,
                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise ValueError("Native local Worker startup failed")
                if "Ready on http://127.0.0.1:" + str(port) in log_path.read_text(errors="replace"):
                    with socket.create_connection(("127.0.0.1", port), timeout=.2):
                        break
                time.sleep(.2)
            else:
                raise ValueError("Native local Worker startup timed out")
            opener = build_opener(ProxyHandler({}), NoRedirect())
            for case in CASES:
                start = time.monotonic()
                request = Request("http://127.0.0.1:" + str(port) + "/", method="POST",
                    headers={"Content-Type": "application/json"}, data=json.dumps({"case": case}).encode())
                with opener.open(request, timeout=10) as response:
                    result = json.loads(response.read(4096))
                elapsed = round((time.monotonic() - start) * 1000)
                assert result["outcome"] == ("accepted" if case == "valid" else "rejected")
                assert result["providerAttempts"] == 1
                if case in {"oversized-header", "oversized-stream"}:
                    assert result["failureCode"] == "JEV_RESPONSE_TOO_LARGE"
                    assert result["failureType"] == "ValueError"
                evidence["cases"].append({**result, "localLatencyMs": elapsed})
            assert observed == list(CASES)
            assert 2700 <= evidence["cases"][-1]["localLatencyMs"] <= 3900
            evidence.update(passed=True, loopbackProviderAttempts=len(observed))
    finally:
        if process is not None and process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
        provider.shutdown()
        provider.server_close()
        (directory / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8793)
    args = parser.parse_args()
    try:
        evidence = run(args.run_dir, args.port)
    except Exception:
        print(json.dumps({"error": "JEV_NATIVE_LOCAL_FAILED"}))
        return 1
    print(json.dumps({"passed": evidence["passed"], "localCases": len(evidence["cases"]),
        "realProviderRequests": 0, "remoteD1Operations": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

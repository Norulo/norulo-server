"""Finite LOCAL native acceptance for disabled payments and CSV streaming.

One synthetic Free Owner creates one expense through the unchanged application.
The fixture has only nonce-protected setup/probe routes, copied outside the
checkout. No remote D1, providers, retries, deployment or browser claim.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import socket
import subprocess
import time
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "cloudflare/server"
HTTP_CAP, SQL_CAP, READ_CAP, WRITE_CAP = 16, 300, 20000, 1000
OWNER, SESSION, CATEGORY = "usr_github_799001", "native-free-billing-csv-local", "cat_native_free_csv"
FIXTURE_NOW = 1791735000
NONCE = "norulo-native-free-billing-csv-fixture-v1"
WORKERD_VERSION = "1.20260921.1"
WORKERD_SHA256 = "eb449c84ddd55ea357dc73e6c1b50bd255ccdc5d1875544c162435b7bd6168b6"
PURPOSE, NOTE = 'Cloud, 费用 "Norulo"\nsecond line', "=SUM(1,2)"
spec = importlib.util.spec_from_file_location("native_csv_dependencies", ROOT / "scripts/check-rest-parity-native-runtime.py")
parity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parity)

ENTRY = r'''
from contextvars import ContextVar
import json
from urllib.parse import urlsplit
from workers import Request, Response
import application_entry as canonical
from norulo_server.cloudflare_native_d1 import NativeD1
from norulo_server.cloudflare_validation_budget import _field
from norulo_server.cloudflare_state_records import record_name, encode_record
from norulo_server.cloudflare_d1_mapping import initialize_account

OWNER,SESSION,CATEGORY="usr_github_799001","native-free-billing-csv-local","cat_native_free_csv"
FIXTURE_NOW=1791735000
NONCE="norulo-native-free-billing-csv-fixture-v1"
context=ContextVar("native_free_billing_csv",default={})
provider_calls=[]
native_totals={"statements":0,"rowsRead":0,"rowsWritten":0}
setup_done=False
class FixtureClock:
    @classmethod
    def time(cls):return FIXTURE_NOW
canonical.time=FixtureClock
class ForbiddenGateway:
    enabled=False
    def __init__(self,env):pass
    def __getattr__(self,name):
        async def blocked(*args,**kwargs):
            provider_calls.append(name)
            raise AssertionError("Providers excluded from finite LOCAL billing/CSV proof")
        return blocked
class ForbiddenPaymentConstruction(ForbiddenGateway):
    def __init__(self,env):
        provider_calls.append("payment-construction")
        raise AssertionError("Disabled payment reads must not construct their provider")
canonical.WorkerGitHubGateway=ForbiddenGateway
canonical.WorkerEmailGateway=ForbiddenGateway
canonical.WorkerJevGateway=ForbiddenGateway
canonical.WorkerCreemGateway=ForbiddenPaymentConstruction

class ObservedStatement:
    def __init__(self,owner,native):
        self.owner,self.native,self.sql,self.params=owner,native,native.sql,native.params
    def bind(self,*params):return ObservedStatement(self.owner,self.native.bind(*params))
    async def all(self):return (await self.owner.batch([self]))[0]
    async def run(self):return await self.all()
    async def first(self,column=None):
        rows=_field(await self.all(),"results",[])
        value=rows[0] if rows else None
        return _field(value,column) if column is not None and value is not None else value
class ObservedNativeD1(NativeD1):
    def __init__(self,binding):
        super().__init__(binding)
        self.observation=context.get()
    def prepare(self,sql):return ObservedStatement(self,super().prepare(sql))
    async def batch(self,statements):
        statements=list(statements)
        assert 0<len(statements)<=64 and all(item.owner is self for item in statements)
        assert native_totals["statements"]+len(statements)<=300
        if self.observation.get("readOnly"):
            assert all(item.sql.lstrip().upper().startswith(("SELECT","WITH")) for item in statements)
        results=list(await super().batch([item.native for item in statements]))
        assert len(results)==len(statements)
        metadata=[]
        for item in results:
            meta=_field(item,"meta")
            reads,writes=_field(meta,"rows_read"),_field(meta,"rows_written")
            assert _field(item,"success") is True and type(reads) is int and type(writes) is int
            assert reads>=0 and writes>=0
            metadata.append({"rowsRead":reads,"rowsWritten":writes,"nativeAttempts":_field(meta,"total_attempts")})
        group={"callId":self.observation["callId"],"phase":self.observation["phase"],"statements":len(results),
            "rowsRead":sum(item["rowsRead"] for item in metadata),"rowsWritten":sum(item["rowsWritten"] for item in metadata),
            "catalogStatements":sum("billing_public_catalog" in item.sql.lower() for item in statements),
            "statementMetadata":metadata}
        for name in native_totals:native_totals[name]+=group[name]
        assert native_totals["rowsRead"]<=20000 and native_totals["rowsWritten"]<=1000
        assert not self.observation.get("readOnly") or group["rowsWritten"]==0
        print(json.dumps({"nativeFreeBillingCsvMeta":group}))
        return results
canonical.NativeD1=ObservedNativeD1
original_csv_stream=canonical._csv_stream
def observed_csv_stream(export):
    print(json.dumps({"nativeFreeBillingCsvStream":{"callId":context.get()["callId"],"canonicalStreamDelegated":True}}))
    return original_csv_stream(export)
canonical._csv_stream=observed_csv_stream

async def commands(native,values):
    return await native.batch([native.prepare(sql).bind(*params) for sql,params in values])
def seed():
    payload=encode_record("users",OWNER,{"id":OWNER,"name":"Synthetic Free CSV Owner",
        "createdAt":FIXTURE_NOW-1000,"billing":{"plan":"free"}})
    return [("INSERT INTO app_state(name,payload,updated_at) VALUES(?,?,?)",(record_name("users",OWNER),payload,FIXTURE_NOW)),
        ("INSERT INTO app_state(name,payload,updated_at) VALUES(?,?,?)",(record_name("sessions",SESSION),
            encode_record("sessions",SESSION,{"id":SESSION,"userId":OWNER,"expiresAt":FIXTURE_NOW+86400}),FIXTURE_NOW)),
        *initialize_account(owner_id=OWNER,account_snapshot=payload,now=FIXTURE_NOW),
        ("INSERT INTO expense_categories(id,owner_id,name,revision,created_at,updated_at) VALUES(?,?,'Hosting',1,'local','local')",(CATEGORY,OWNER))]
PROBE_SQL=(
    "SELECT id,owner_id,target_kind,project_id,amount_minor,currency,occurred_on,purpose,note,quantity_decimal,unit,revision FROM expenses WHERE deleted_at IS NULL LIMIT 2",
    "SELECT expense_id,owner_id,actor_kind,actor_id FROM expense_events LIMIT 2",
    "SELECT owner_id,records,writes,minute_writes,month,record_cap,minute_cap,month_cap,jev_reserved_microusd FROM ledger_plan_usage LIMIT 2",
    "SELECT owner_id,plan,dirty FROM account_entitlement_authority LIMIT 2",
    "SELECT COUNT(*) total FROM billing_public_catalog",
    "SELECT name FROM d1_migrations ORDER BY id LIMIT 14",
    "SELECT COUNT(*) total FROM d1_command_guard",
)
class Default(canonical.Default):
    async def fetch(self,request):
        global setup_done
        raw=await request.bytes()
        raw=raw if isinstance(raw,bytes) else raw.to_bytes()
        assert len(raw)<=8192
        request=Request(str(request.url),method=str(request.method),headers=dict(request.headers.items()),body=raw if raw else None)
        path=urlsplit(str(request.url)).path
        call_id=str(request.headers.get("x-native-call-id") or "")
        assert call_id.isdigit() and 1<=int(call_id)<=16
        private=path.startswith("/_fixture/")
        if private and request.headers.get("x-native-fixture-nonce")!=NONCE:
            return Response.json({"error":{"code":"LOCAL_FIXTURE_NONCE_REQUIRED"}},status=403)
        phase="fixture-setup" if path=="/_fixture/setup" else "integrity-probe" if private else "application"
        read_only=str(request.method)=="GET"
        token=context.set({"callId":call_id,"phase":phase,"readOnly":read_only})
        try:
            if path=="/_fixture/setup":
                assert not setup_done and str(request.method)=="POST"
                native=ObservedNativeD1(self.env.DB)
                empty=await native.prepare("SELECT COUNT(*) total FROM app_state WHERE name GLOB 'record:users:*'").first()
                assert empty["total"]==0
                await commands(native,seed())
                setup_done=True
                return Response.json({"syntheticFreeOwners":1,"seededExpenseRows":0})
            if path=="/_fixture/probe":
                assert setup_done and str(request.method)=="GET"
                result=await commands(ObservedNativeD1(self.env.DB),[(sql,()) for sql in PROBE_SQL])
                rows=[[dict(row) for row in _field(part,"results",[])] for part in result]
                assert provider_calls==[]
                return Response.json({"expenses":rows[0],"events":rows[1],"usage":rows[2],"authority":rows[3],
                    "catalogRows":rows[4][0]["total"],"migrationNames":[row["name"] for row in rows[5]],
                    "commandGuards":rows[6][0]["total"],"providerCalls":0})
            if private:return Response.json({"error":{"code":"NOT_FOUND"}},status=404)
            return await super().fetch(request)
        finally:context.reset(token)
'''


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def stop(process):
    if process is not None and process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)


def assert_free_catalog(payload, *, authenticated, records=0):
    assert payload["provider"] == "disabled" and payload["enabled"] is False
    assert payload["page"]["checkoutAction"] is None
    plans = {plan["id"]: plan for plan in payload["plans"]}
    assert set(plans) == {"free", "pro", "max"}
    free = plans["free"]
    assert free["prices"]["month"] == {"amount": "0", "currency": "USD", "interval": "month", "configured": True}
    assert free["entitlements"]["limits"] == {"projects": 3, "expenseRecords": 100, "writesPerMinute": 10, "writesPerMonth": 1000}
    assert free["entitlements"]["jev"]["eligible"] is False
    for plan in (plans["pro"], plans["max"]):
        for interval in ("month", "year"):
            price = plan["prices"][interval]
            assert price["amount"] is None and price["configured"] is False and price["productId"] is None
    assert ("account" in payload) == ("ledgerUsage" in payload) == authenticated
    if authenticated:
        assert payload["account"]["plan"] == "free"
        assert payload["ledgerUsage"]["expenseRecords"] == {"used": records, "limit": 100, "remaining": 100-records}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8953)
    parser.add_argument("--tzdata-cache", type=Path)
    args = parser.parse_args()
    directory = args.run_dir.resolve()
    if not directory.is_relative_to(Path("/workspace")) or not 1024 <= args.port <= 64535:
        raise SystemExit("Use a fresh /workspace directory and an unprivileged port")
    directory.mkdir(parents=True, exist_ok=False)
    subprocess.run([os.sys.executable, str(WORKER / "sync_server_modules.py"), "--check"], cwd=ROOT, check=True)
    canonical = sorted((ROOT / "norulo_server").glob("*.py"))
    packaged = sorted((WORKER / "src/norulo_server").glob("*.py"))
    assert {path.name for path in canonical} == {path.name for path in packaged}
    assert (WORKER / "src/norulo_server/__init__.py").read_bytes() == b""
    assert all(path.name == "__init__.py" or path.read_bytes() == (WORKER / "src/norulo_server" / path.name).read_bytes() for path in canonical)
    source = directory / "src"
    source.mkdir()
    (source / "entry.py").write_text(ENTRY)
    shutil.copy2(WORKER / "src/entry.py", source / "application_entry.py")
    shutil.copytree(WORKER / "src/norulo_server", source / "norulo_server", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copytree(WORKER / "python_modules", directory / "python_modules", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    package_root, package_manifest = parity.pinned_tzdata(args.tzdata_cache)
    shutil.copytree(package_root / "tzdata", directory / "python_modules/tzdata", dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    dependencies = ("pyproject.toml", "uv.lock", "pylock.toml", "package.json", "package-lock.json")
    for name in dependencies:
        shutil.copy2(WORKER / name, directory / name)
    (directory / "node_modules").symlink_to(WORKER / "node_modules", target_is_directory=True)
    base = f"http://127.0.0.1:{args.port}"
    config = {"name": "norulo-free-billing-csv-native-local-only", "main": "src/entry.py",
        "compatibility_date": "2026-09-23", "compatibility_flags": ["python_workers"],
        "workers_dev": False, "preview_urls": False, "routes": [],
        "vars": {"NORULO_MODE": "production", "NORULO_D1_ACCESS_ENABLED": "1",
            "NORULO_PREVIEW_PRODUCT_ENABLED": "0", "NORULO_RECURRING_EXPENSES_ENABLED": "0",
            "NORULO_APP_URL": "https://norulo.com", "NORULO_ALLOWED_ORIGINS": base,
            "NORULO_CREEM_PRODUCT_IDS_JSON": "{}", "NORULO_EMAIL_AUTH_ENABLED": "0",
            "NORULO_JEV_SUGGESTIONS_ENABLED": "0", "NORULO_JEV_SUGGESTIONS_EVALUATED": "0"},
        "d1_databases": [{"binding": "DB", "database_name": "free-billing-csv-native-local-only",
            "database_id": "00000000-0000-0000-0000-000000000049", "remote": False,
            "migrations_dir": str(WORKER / "migrations")}]}
    config_path = directory / "wrangler.jsonc"
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    bundle = Path("/workspace/.cache/norulo-pyodide/pyodide_314.0.6_2026-08-17_6.capnp.bin")
    assert bundle.is_file() and parity.sha256(bundle) == parity.BUNDLE_SHA256
    binary = WORKER / "node_modules/@cloudflare/workerd-linux-64/bin/workerd"
    assert json.loads((binary.parents[1] / "package.json").read_text())["version"] == WORKERD_VERSION
    assert parity.sha256(binary) == WORKERD_SHA256
    wrapper = directory / "workerd-local-cache.sh"
    wrapper.write_text("#!/bin/sh\nexec " + shlex.quote(str(binary)) + ' "$@" --pyodide-bundle-disk-cache-dir=/workspace/.cache/norulo-pyodide\n')
    wrapper.chmod(0o700)
    env = {key: value for key, value in os.environ.items() if key not in {"CLOUDFLARE_API_TOKEN", "TYPESAFE_API_KEY"}}
    env.update({"XDG_CACHE_HOME": "/workspace/.cache", "XDG_CONFIG_HOME": "/workspace/.cache/config",
        "UV_CACHE_DIR": "/workspace/.cache/uv", "UV_PYTHON_INSTALL_DIR": "/workspace/.cache/python",
        "UV_SYSTEM_CERTS": "true", "NPM_CONFIG_CACHE": str(directory / "npm-cache"),
        "WRANGLER_SEND_METRICS": "false", "CI": "1", "MINIFLARE_WORKERD_PATH": str(wrapper),
        "WRANGLER_LOG_PATH": str(directory / "wrangler-debug.log")})
    manifest = [(str(path.relative_to(source)), parity.sha256(path)) for path in sorted((source / "norulo_server").glob("*.py"))]
    evidence = {"passed": False, "date": "2026-10-11", "localOnly": True,
        "remoteD1Operations": 0, "realProviderRequests": 0, "remoteApplicationRequests": 0,
        "browserEndToEndClaimed": False, "realUserFlowClaimed": False, "clientRetries": 0,
        "syntheticFreeOwners": 1, "maximumCreatedExpenses": 1, "commercialPolicyUnchanged": True,
        "localHttpCap": HTTP_CAP, "localObservedCaps": {"statements": SQL_CAP, "rowsRead": READ_CAP, "rowsWritten": WRITE_CAP},
        "fixtureRoutesNonceProtected": True, "fixtureRoutesOutsideCheckoutOnly": True,
        "fixtureClock": FIXTURE_NOW, "packagedNamespaceVerified": True, "blankPackagedInitializerVerified": True,
        "packagedSourceModuleCount": len(manifest) - 1, "sourceSha256": dict(manifest),
        "canonicalRootSourceSha256": {path.name: parity.sha256(path) for path in canonical},
        "canonicalSourceTreeSha256": hashlib.sha256(json.dumps(manifest, separators=(",", ":")).encode()).hexdigest(),
        "canonicalApplicationEntrySha256": parity.sha256(source / "application_entry.py"),
        "fixtureEntrySha256": parity.sha256(source / "entry.py"), "driverSha256": parity.sha256(Path(__file__)),
        "localConfigSha256": parity.sha256(config_path), "dependencySha256": {name: parity.sha256(directory / name) for name in dependencies},
        "runtimeProvenance": {"workerdVersion": WORKERD_VERSION, "workerdSha256": WORKERD_SHA256,
            "pythonBundleSha256": parity.BUNDLE_SHA256, "tzdataVersion": parity.PINNED_TZDATA_VERSION,
            "tzdataManifestSha256": hashlib.sha256(json.dumps(package_manifest, separators=(",", ":")).encode()).hexdigest()},
        "localMigrationSetup": {"includedInNativeTotals": False, "localOnly": True,
            "files": {path.name: parity.sha256(path) for path in sorted((WORKER / "migrations").glob("*.sql"))}}}
    process, attempts, cases = None, 0, []
    log_path = directory / "runtime.log"
    cli = ["node", str(WORKER / "node_modules/wrangler/bin/wrangler.js")]
    opener = build_opener(ProxyHandler({}), NoRedirect())
    def call(name, path, *, method="GET", body=None, cookie=False, expected=200, nonce=True, csv_body=False):
        nonlocal attempts
        attempts += 1
        assert attempts <= HTTP_CAP
        headers = {"X-Native-Call-Id": str(attempts), "Content-Type": "application/json"}
        if path.startswith("/_fixture/") and nonce:
            headers["X-Native-Fixture-Nonce"] = NONCE
        if cookie:
            headers["Cookie"] = "nr_session=" + SESSION
        if method == "POST":
            headers.update({"Origin": base, "Idempotency-Key": "native-free-billing-csv-local"})
        request = Request(base + path, method=method, headers=headers,
            data=json.dumps(body, separators=(",", ":")).encode() if body is not None else None)
        try:
            response = opener.open(request, timeout=60)
        except HTTPError as error:
            response = error
        with response:
            raw = response.read()
            assert len(raw) <= 32768
            result = raw.decode("utf-8") if csv_body else json.loads(raw)
            cases.append({"name": name, "callId": str(attempts), "path": path, "method": method,
                "status": response.status, "responseHeaders": dict(response.headers), "result": result})
            assert response.status == expected, (name, response.status)
            return result
    try:
        with (directory / "migration.log").open("w") as log:
            completed = subprocess.run([*cli, "d1", "migrations", "apply", "DB", "--local", "--config", str(config_path),
                "--persist-to", str(directory / "state")], cwd=directory, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=120)
            assert completed.returncode == 0
        with log_path.open("w") as log:
            process = subprocess.Popen([*cli, "dev", "--local", "--config", str(config_path), "--ip", "127.0.0.1",
                "--port", str(args.port), "--inspector-port", str(args.port + 1000), "--persist-to", str(directory / "state")],
                cwd=directory, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                assert process.poll() is None, "Native Worker startup failed"
                if f"Ready on http://127.0.0.1:{args.port}" in log_path.read_text(errors="replace"):
                    try:
                        with socket.create_connection(("127.0.0.1", args.port), timeout=.2):
                            break
                    except OSError:
                        pass
                time.sleep(.2)
            else:
                raise AssertionError("Native Worker startup timed out")
            call("fixture_nonce_rejected", "/_fixture/setup", method="POST", body={}, nonce=False, expected=403)
            call("setup", "/_fixture/setup", method="POST", body={})
            assert_free_catalog(call("public_free_catalog", "/billing/plan"), authenticated=False)
            assert_free_catalog(call("cookie_free_catalog", "/billing/plan", cookie=True), authenticated=True)
            account = call("cookie_billing", "/billing", cookie=True)
            assert account["account"]["plan"] == "free" and account["ledgerUsage"]["expenseRecords"] == {"used": 0, "limit": 100, "remaining": 100}
            call("anonymous_billing_rejected", "/billing", expected=401)
            expense = call("expense_create", "/api/v1/expenses", method="POST", cookie=True, expected=201,
                body={"target": {"kind": "shared"}, "categoryId": CATEGORY, "occurredOn": "2026-10-11",
                    "amount": "12.34", "currency": "USD", "purpose": PURPOSE, "note": NOTE, "quantity": "2.5", "unit": "units"})
            assert expense["amount"] == "12.34" and expense["purpose"] == PURPOSE
            summary = call("report_summary", "/api/v1/reports/summary?target=shared", cookie=True)
            assert summary["groups"] and all(group["currency"] == "USD" and str(group["amountMinor"]) == "1234" for group in summary["groups"])
            text = call("csv_native_stream", "/api/v1/expenses/export?target=shared", cookie=True, csv_body=True)
            rows = list(csv.DictReader(io.StringIO(text, newline="")))
            assert len(rows) == 1 and rows[0] == {"id": expense["id"], "target": "shared", "projectId": "",
                "occurredOn": "2026-10-11", "amountMinor": "1234", "currency": "USD", "categoryId": CATEGORY,
                "purpose": PURPOSE, "note": "'" + NOTE, "quantity": "2.5", "unit": "units"}
            empty = call("csv_native_empty_stream", "/api/v1/expenses/export?from=2026-09-01&to=2026-09-02", cookie=True, csv_body=True)
            assert not list(csv.DictReader(io.StringIO(empty, newline=""))) and empty.splitlines()[0] == text.splitlines()[0]
            assert_free_catalog(call("cookie_catalog_after_expense", "/billing/plan", cookie=True), authenticated=True, records=1)
            final = call("final", "/_fixture/probe")
            assert len(final["expenses"]) == len(final["events"]) == len(final["usage"]) == len(final["authority"]) == 1
            assert final["expenses"][0]["id"] == final["events"][0]["expense_id"] == expense["id"]
            usage = final["usage"][0]
            assert usage["records"] == usage["writes"] == usage["minute_writes"] == 1
            assert (usage["record_cap"], usage["minute_cap"], usage["month_cap"], usage["jev_reserved_microusd"]) == (100, 10, 1000, 0)
            assert final["authority"] == [{"owner_id": OWNER, "plan": "free", "dirty": 0}]
            assert final["catalogRows"] == final["commandGuards"] == final["providerCalls"] == 0
            assert final["migrationNames"] == [path.name for path in sorted((WORKER / "migrations").glob("*.sql"))]
        evidence["passed"] = True
    except Exception as error:
        evidence["failure"] = {"type": type(error).__name__, "detail": str(error)[:240]}
    finally:
        stop(process)
        groups, streams = [], []
        for line in log_path.read_text(errors="replace").splitlines() if log_path.exists() else []:
            if line.startswith('{"nativeFreeBillingCsvMeta":'):
                groups.append(json.loads(line)["nativeFreeBillingCsvMeta"])
            elif line.startswith('{"nativeFreeBillingCsvStream":'):
                streams.append(json.loads(line)["nativeFreeBillingCsvStream"])
        by_call = defaultdict(lambda: {"statements": 0, "rowsRead": 0, "rowsWritten": 0, "catalogStatements": 0})
        for group in groups:
            for key in by_call[group["callId"]]:
                by_call[group["callId"]][key] += group[key]
        evidence.update(cases=cases, nativeGroups=groups, nativeCsvStreams=streams, perCallNativeMetadata=dict(by_call),
            localHttpRequestsAttempted=attempts, localHttpRequestsCompleted=len(cases),
            nativeStatements=sum(group["statements"] for group in groups), nativeRowsRead=sum(group["rowsRead"] for group in groups),
            nativeRowsWritten=sum(group["rowsWritten"] for group in groups),
            nativeAttemptsObserved=sorted({part["nativeAttempts"] for group in groups for part in group["statementMetadata"]}, key=str),
            runtimeStopped=process is None or process.poll() is not None)
        if evidence["passed"]:
            try:
                assert len(cases) == attempts == 12 <= HTTP_CAP
                assert evidence["nativeStatements"] <= SQL_CAP and evidence["nativeRowsRead"] <= READ_CAP and evidence["nativeRowsWritten"] <= WRITE_CAP
                names = {case["name"]: case for case in cases}
                assert by_call[names["public_free_catalog"]["callId"]]["statements"] == 0
                assert by_call[names["fixture_nonce_rejected"]["callId"]]["statements"] == 0
                for case in cases:
                    if case["method"] == "GET":
                        assert by_call[case["callId"]]["rowsWritten"] == 0
                    if case["path"].startswith("/billing"):
                        assert by_call[case["callId"]]["catalogStatements"] == 0
                assert {stream["callId"] for stream in streams} == {names["csv_native_stream"]["callId"], names["csv_native_empty_stream"]["callId"]}
                assert all(stream["canonicalStreamDelegated"] is True for stream in streams)
                for name in ("csv_native_stream", "csv_native_empty_stream"):
                    headers = {key.lower(): value for key, value in names[name]["responseHeaders"].items()}
                    assert headers["content-type"] == "text/csv; charset=utf-8"
                    assert headers["content-disposition"] == 'attachment; filename="expenses.csv"'
                    assert headers["cache-control"] == "no-store"
                evidence["acceptance"] = {"publicDisabledCatalogZeroD1": True, "cookieCatalogAndBillingReadOnly": True,
                    "disabledCatalogNeverReadOrWritten": True, "paymentProviderNotConstructed": True,
                    "actualNativeCsvReadableStreamAndUnicodeQuoting": True, "actualCsvFormulaCellPrefixed": True,
                    "emptyCsvHeaderOnly": True, "singleRealHttpExpenseWithFreeQuota": True,
                    "nonceRejectionBeforeD1": True, "commercialFreeCapsUnchanged": True}
            except Exception as error:
                evidence["passed"] = False
                evidence["acceptanceFailure"] = {"type": type(error).__name__, "detail": str(error)[:240]}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: evidence.get(key) for key in ("passed", "failure", "acceptanceFailure", "localHttpRequestsCompleted",
        "nativeStatements", "nativeRowsRead", "nativeRowsWritten", "runtimeStopped")}, sort_keys=True))
    return 0 if evidence["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

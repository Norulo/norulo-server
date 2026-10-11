"""Historical singleton scheduler proof against independent LOCAL Workerd D1/DO.

All account/session/category/rule data is synthetic and local. The real canonical
Default.scheduled, production coordinator, NativeD1 and commercial plan adapter
execute unchanged. The wrapper adds bounded LOCAL setup, clock and probe seams.
No Cloudflare API, provider, remote database, deployed route or client retry.
This fixture applies to the earlier singleton implementation. Current Owner
fanout must use check-production-recurring-load-native-local.py instead.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
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
spec = importlib.util.spec_from_file_location("recurring_native_dependencies", ROOT / "scripts/check-rest-parity-native-runtime.py")
parity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parity)
FIXTURE_NOW = 1791735000  # 2026-10-11 16:10:00 UTC, a synthetic clock.
OWNER = "usr_github_795001"
HTTP_CAP = 24
PINNED_WORKERD_VERSION = "1.20260921.1"
PINNED_WORKERD_SHA256 = "eb449c84ddd55ea357dc73e6c1b50bd255ccdc5d1875544c162435b7bd6168b6"
READ_CAP, WRITE_CAP = 50000, 3000  # Finite local proof limits, never product policy.
ENTRY = r'''
import hashlib
import json
from types import SimpleNamespace
from urllib.parse import urlsplit
from workers import Response, Request
import application_entry as canonical
from norulo_server.cloudflare_native_d1 import NativeD1
from norulo_server.cloudflare_validation_budget import _field
from norulo_server.cloudflare_d1_mapping import initialize_account
from norulo_server.cloudflare_state_records import record_name, encode_record
from norulo_server.cloudflare_recurring_scheduler import (
    PRODUCTION_RECURRING_CRON, RECURRING_SCHEDULER_SCOPE, RecurringJournal)

FIXTURE_NOW=1791735000
OWNER="usr_github_795001"
TABLES=("app_state","account_entitlement_authority","expense_categories","expenses",
    "expense_events","expense_recurring_rules","expense_recurring_occurrences",
    "expense_recurring_pending","ledger_activity_events","ledger_plan_usage","d1_command_guard","d1_migrations")
phase="application"
provider_calls=[]
class FixtureClock:
    now=FIXTURE_NOW
    @classmethod
    def time(cls): return cls.now
canonical.time=FixtureClock

class ForbiddenGateway:
    def __init__(self,env): pass
    def __getattr__(self,name):
        async def blocked(*args,**kwargs):
            provider_calls.append(name)
            raise AssertionError("Provider dispatch excluded from finite local proof")
        return blocked
canonical.WorkerGitHubGateway=ForbiddenGateway
canonical.WorkerCreemGateway=ForbiddenGateway
canonical.WorkerJevGateway=ForbiddenGateway
canonical.WorkerEmailGateway=ForbiddenGateway

class ObservedStatement:
    def __init__(self,owner,native):
        self.owner,self.native,self.sql,self.params=owner,native,native.sql,native.params
    def bind(self,*params): return ObservedStatement(self.owner,self.native.bind(*params))
    async def all(self): return (await self.owner.batch([self]))[0]
    async def run(self): return await self.all()
    async def first(self,column=None):
        rows=_field(await self.all(),"results",[])
        row=rows[0] if rows else None
        return _field(row,column) if column is not None and row is not None else row
class ObservedNativeD1(NativeD1):
    def prepare(self,sql): return ObservedStatement(self,super().prepare(sql))
    async def batch(self,statements):
        statements=list(statements)
        assert 0<len(statements)<=64 and all(item.owner is self for item in statements)
        result=list(await super().batch([item.native for item in statements]))
        assert len(result)==len(statements)
        values=[]
        for part in result:
            meta=_field(part,"meta")
            reads,writes=_field(meta,"rows_read"),_field(meta,"rows_written")
            assert _field(part,"success") is True
            assert type(reads) is int and type(writes) is int and reads>=0 and writes>=0
            values.append({"rowsRead":reads,"rowsWritten":writes,"nativeAttempts":_field(meta,"total_attempts")})
        print(json.dumps({"productionRecurringNativeMeta":{"phase":phase,"statements":len(result),
            "rowsRead":sum(item["rowsRead"] for item in values),
            "rowsWritten":sum(item["rowsWritten"] for item in values),"statementMetadata":values}}))
        return result
canonical.NativeD1=ObservedNativeD1

async def commands(native,values):
    return await native.batch([native.prepare(sql).bind(*params) for sql,params in values])
def seed():
    user={"id":OWNER,"name":"Synthetic production recurring owner","createdAt":FIXTURE_NOW-1000,
        "billing":{"plan":"free"}}
    payload=encode_record("users",OWNER,user)
    return [("INSERT INTO app_state(name,payload,updated_at) VALUES(?,?,?)",
        (record_name("users",OWNER),payload,FIXTURE_NOW)),
        ("INSERT INTO app_state(name,payload,updated_at) VALUES(?,?,?)",
        (record_name("sessions","production-recurring-native-owner"),encode_record("sessions","production-recurring-native-owner",
            {"id":"production-recurring-native-owner","userId":OWNER,"expiresAt":FIXTURE_NOW+3*86400}),FIXTURE_NOW)),
        *initialize_account(owner_id=OWNER,account_snapshot=payload,now=FIXTURE_NOW),
        ("INSERT INTO expense_categories(id,owner_id,name,revision,created_at,updated_at) VALUES(?,?,'Hosting',1,'local','local')",
        ("cat_production_recurring",OWNER)),
        ("""INSERT INTO ledger_activity_events(id,operation_id,owner_id,target_kind,project_id,
        actor_json,resource_kind,resource_id,action,created_at)
        VALUES('act_expired_synthetic','local-expired',?,'shared',NULL,'{}','expense','exp_synthetic_expired','create','2020-01-01T00:00:00Z')""",(OWNER,))]

async def snapshot(env,journal):
    global phase
    phase="integrity-probe"
    parts=await commands(ObservedNativeD1(env.DB),[("SELECT * FROM "+table,()) for table in TABLES])
    rows={table:[dict(row) for row in _field(part,"results",[])] for table,part in zip(TABLES,parts)}
    tables={}
    for table,items in rows.items():
        items.sort(key=lambda row:json.dumps(row,sort_keys=True,separators=(",",":")))
        tables[table]={"rows":len(items),"sha256":hashlib.sha256(json.dumps(items,
            sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()}
    assert len(rows["expenses"])<=1 and len(rows["expense_recurring_rules"])<=1
    assert len(rows["expense_recurring_occurrences"])<=1 and len(rows["ledger_plan_usage"])<=1
    assert len(rows["d1_migrations"])==12 and not rows["d1_command_guard"]
    assert not provider_calls
    return {"tables":tables,"journal":journal.snapshot(),"expenses":rows["expenses"],
        "events":rows["expense_events"],"occurrences":rows["expense_recurring_occurrences"],
        "rules":rows["expense_recurring_rules"],"usage":rows["ledger_plan_usage"],
        "authority":rows["account_entitlement_authority"],
        "expiredActivityPresent":any(row["id"]=="act_expired_synthetic" for row in rows["ledger_activity_events"]),
        "migrationNames":[row["name"] for row in sorted(rows["d1_migrations"],key=lambda row:row["id"])],
        "providerCalls":0}

class Default(canonical.Default):
    async def fetch(self,request):
        global phase
        path=urlsplit(str(request.url)).path
        raw=await request.bytes()
        raw=raw if isinstance(raw,bytes) else raw.to_bytes()
        assert len(raw)<=8192
        request=Request(str(request.url),method=str(request.method),headers=dict(request.headers.items()),body=raw if raw else None)
        namespace=self.env.RECURRING_SCHEDULER
        stub=namespace.get(namespace.idFromName(RECURRING_SCHEDULER_SCOPE))
        if path=="/_fixture/tick":
            status,code=200,None
            try:
                await super().scheduled(SimpleNamespace(cron=PRODUCTION_RECURRING_CRON,scheduledTime=float(FIXTURE_NOW*1000)),self.env,self.ctx)
            except RuntimeError as error:
                assert str(error)=="RECURRING_EXECUTION_UNAVAILABLE"
                status,code=503,str(error)
            response=await stub.fetch(Request(str(request.url).replace('/_fixture/tick','/_fixture/probe'),method="GET",headers=dict(request.headers.items())))
            body=json.loads(await response.text())
            body["productionCron"]=PRODUCTION_RECURRING_CRON
            body["canonicalDefaultScheduledCompleted"]=status==200
            body["strictBooleanRpcSuccessAccepted"]=status==200
            if code: body["defaultFailureCode"]=code
            return Response.json(body,status=status)
        if path.startswith("/_fixture/"):
            return await stub.fetch(request)
        phase="application"
        return await super().fetch(request)

class RecurringScheduler(canonical.RecurringScheduler):
    async def runRecurring(self):
        global phase
        FixtureClock.now=int(await self.ctx.storage.get("fixtureNow") or FIXTURE_NOW)
        phase="scheduler"
        result=await super().runRecurring()
        await self.ctx.storage.put("fixtureLastResult",json.dumps(result,separators=(",",":")))
        return result
    async def fetch(self,request):
        global phase
        path=urlsplit(str(request.url)).path
        count=int(request.headers.get("x-native-fixture-call") or "0")
        assert int(await self.ctx.storage.get("fixtureHttpCalls") or 0)<count<=24
        await self.ctx.storage.put("fixtureHttpCalls",count)
        FixtureClock.now=int(await self.ctx.storage.get("fixtureNow") or FIXTURE_NOW)
        if self.journal is None: self.journal=RecurringJournal(self.ctx.storage.sql)
        if path=="/_fixture/setup":
            assert count==1
            phase="fixture-setup"
            await commands(ObservedNativeD1(self.env.DB),seed())
            await self.ctx.storage.put("fixtureNow",float(FIXTURE_NOW))
        elif path=="/_fixture/advance-clock":
            advances=int(await self.ctx.storage.get("fixtureAdvances") or 0)+1
            assert advances<=2
            FixtureClock.now=FIXTURE_NOW+86400+(3600 if advances==2 else 0)
            await self.ctx.storage.put("fixtureAdvances",float(advances))
            await self.ctx.storage.put("fixtureNow",float(FixtureClock.now))
        elif path=="/_fixture/park-unknown":
            assert self.journal.snapshot()["state"]=="idle"
            FixtureClock.now+=3600
            assert self.journal.begin(FixtureClock.now//3600) is True
            await self.ctx.storage.put("fixtureNow",float(FixtureClock.now))
        elif path not in {"/_fixture/probe","/_fixture/final"}:
            return await super().fetch(request)
        last=await self.ctx.storage.get("fixtureLastResult")
        integrity=await snapshot(self.env,self.journal)
        return Response.json({"integrity":integrity,"result":json.loads(str(last)) if last else None,
            "fixtureClock":FixtureClock.now,"fixedScope":RECURRING_SCHEDULER_SCOPE})

class EmailAdmission(canonical.EmailAdmission): pass
'''


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args): return None


def stop(process):
    if process is not None and process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try: process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)


def verify(cases, groups):
    by_name={item["name"]:item["result"] for item in cases}
    setup,empty=by_name["setup"],by_name["idle_with_expired_activity"]
    assert empty["canonicalDefaultScheduledCompleted"] and empty["strictBooleanRpcSuccessAccepted"]
    assert empty["productionCron"]=="10 16 * * *"
    assert empty["result"]["ok"] is True and empty["result"]["scanned"]==0
    assert empty["result"]["metrics"]["rowsWritten"]==0
    assert empty["integrity"]["tables"]==setup["integrity"]["tables"] and empty["integrity"]["expiredActivityPresent"]
    for name in ("same_hour_empty_replay","same_hour_after_rule_creation","same_hour_due_replay","cold_restart_same_hour"):
        item=by_name[name]
        assert item["strictBooleanRpcSuccessAccepted"] and item["result"]["skipped"] is True,name
        assert item["result"]["metrics"]=={"operations":0,"rowsRead":0,"rowsWritten":0,"complete":True},name
    before,due=by_name["before_due"],by_name["due_shared_rule"]
    assert due["result"]["ok"] is True and due["result"]["created"]==1 and due["result"]["scanned"]==1
    assert due["result"]["blocked"]==due["result"]["replayed"]==0
    assert due["result"]["metrics"]["complete"] is True
    rows=due["integrity"]
    assert len(rows["expenses"])==len(rows["events"])==len(rows["occurrences"])==1
    expense,event,occurrence=rows["expenses"][0],rows["events"][0],rows["occurrences"][0]
    assert expense["owner_id"]==OWNER and expense["target_kind"]=="shared" and expense["project_id"] is None
    assert expense["amount_minor"]==1234 and expense["currency"]=="USD" and expense["occurred_on"]=="2026-10-12"
    assert expense["category_id"]=="cat_production_recurring" and expense["deleted_at"] is None
    assert occurrence["expense_id"]==expense["id"] and occurrence["period_key"]=="M2026-10"
    assert event["expense_id"]==expense["id"] and event["actor_kind"]=="schedule"
    assert rows["rules"][0]["actor_user_id"]==OWNER and rows["rules"][0]["next_occurrence_on"]=="2026-11-12"
    assert rows["usage"][0]["owner_id"]==OWNER and rows["usage"][0]["records"]==1
    before_writes=before["integrity"]["usage"][0]["writes"] if before["integrity"]["usage"] else 0
    assert rows["usage"][0]["writes"]==before_writes+1
    assert rows["authority"][0]["owner_id"]==OWNER and rows["authority"][0]["plan"]=="free"
    for name in ("same_hour_due_replay","cold_restart_same_hour","idle_future_hour"):
        item=by_name[name]
        assert item["integrity"]["tables"]==rows["tables"],name
        assert item["result"]["metrics"]["rowsWritten"]==0,name
    future=by_name["idle_future_hour"]
    assert future["result"]["scanned"]==future["result"]["created"]==0
    assert future["result"]["metrics"]["rowsRead"]>=0
    for name in ("cold_restart_unknown_stopped","unknown_replay_stopped"):
        item=by_name[name]
        assert item["result"]["ok"] is False and item["result"]["error"]=="RECURRING_OUTCOME_UNKNOWN",name
        assert item["defaultFailureCode"]=="RECURRING_EXECUTION_UNAVAILABLE"
        assert item["integrity"]["journal"]["state"]=="active" and item["integrity"]["tables"]==rows["tables"]
        assert "metrics" not in item["result"]  # The durable fence rejected before D1 creation.
    assert sum(item["rowsRead"] for item in groups)<=READ_CAP
    assert sum(item["rowsWritten"] for item in groups)<=WRITE_CAP
    assert all(item["rowsWritten"]==0 for item in groups if item["phase"]=="integrity-probe")
    scheduler=[item for item in groups if item["phase"]=="scheduler"]
    # Three attempted hours: initial schema+idle, due financial work, future idle.
    metrics=[by_name[name]["result"]["metrics"] for name in ("idle_with_expired_activity","due_shared_rule","idle_future_hour")]
    assert sum(item["operations"] for item in metrics)==sum(item["statements"] for item in scheduler)
    assert sum(item["rowsRead"] for item in metrics)==sum(item["rowsRead"] for item in scheduler)
    assert sum(item["rowsWritten"] for item in metrics)==sum(item["rowsWritten"] for item in scheduler)


def require_historical_singleton_core():
    tree = ast.parse((WORKER / "src/entry.py").read_text(encoding="utf-8"))
    coordinator = next((node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "RecurringScheduler"), None)
    if coordinator is None:
        raise SystemExit("Historical recurring fixture requires the singleton RecurringScheduler entry")
    methods = {node.name for node in coordinator.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    if methods & {"runOwnerChunk", "ownerProgress"}:
        raise SystemExit(
            "This historical singleton fixture cannot validate the current Owner scheduler. "
            "No fixture directory or database was created. Use "
            "scripts/check-production-recurring-load-native-local.py --occurrences 8 "
            "--run-dir /workspace/.norulo-environment/recurring-load-FRESH "
            "--output /workspace/.norulo-environment/recurring-load-FRESH/evidence.json")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--port",type=int,default=8946)
    parser.add_argument("--tzdata-cache",type=Path)
    args=parser.parse_args()
    require_historical_singleton_core()
    directory=args.run_dir.resolve()
    if not directory.is_relative_to(Path("/workspace")) or not 1024<=args.port<=64535:
        raise SystemExit("Use a fresh /workspace directory and an unprivileged port")
    directory.mkdir(parents=True,exist_ok=False)
    # Use the exact current packaged namespace, including its blank initializer.
    # Canonical module bytes and package closure are verified before a native run.
    coordinator=ROOT/"norulo_server/cloudflare_recurring_scheduler.py"
    production_cron=next(ast.literal_eval(node.value) for node in ast.parse(coordinator.read_text()).body
        if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name)
            and target.id=="PRODUCTION_RECURRING_CRON" for target in node.targets))
    if production_cron!="10 16 * * *":
        raise SystemExit("Native proof expects the reviewed daily 16:10 UTC production cron")
    subprocess.run([str(Path(os.sys.executable)),str(WORKER/"sync_server_modules.py"),"--check"],cwd=ROOT,check=True)
    canonical_files=sorted((ROOT/"norulo_server").glob("*.py"))
    packaged_files=sorted((WORKER/"src/norulo_server").glob("*.py"))
    if {path.name for path in canonical_files}!={path.name for path in packaged_files}:
        raise SystemExit("Native proof requires exact canonical and packaged module namespace equivalence")
    for path in canonical_files:
        mirrored=WORKER/"src/norulo_server"/path.name
        if path.name!="__init__.py" and path.read_bytes()!=mirrored.read_bytes():
            raise SystemExit("Native proof found an outdated packaged module")
    if (WORKER/"src/norulo_server/__init__.py").read_bytes()!=b"":
        raise SystemExit("Native proof expects the canonical packaging blank initializer")
    source=directory/"src"; source.mkdir()
    (source/"entry.py").write_text(ENTRY,encoding="utf-8")
    shutil.copy2(WORKER/"src/entry.py",source/"application_entry.py")
    shutil.copytree(WORKER/"src/norulo_server",source/"norulo_server",ignore=shutil.ignore_patterns("__pycache__","*.pyc"))
    shutil.copytree(WORKER/"python_modules",directory/"python_modules",ignore=shutil.ignore_patterns("__pycache__","*.pyc"))
    package_root,package_manifest=parity.pinned_tzdata(args.tzdata_cache)
    shutil.copytree(package_root/"tzdata",directory/"python_modules/tzdata",dirs_exist_ok=True,ignore=shutil.ignore_patterns("__pycache__","*.pyc"))
    dependencies=("pyproject.toml","uv.lock","pylock.toml","package.json","package-lock.json")
    for name in dependencies: shutil.copy2(WORKER/name,directory/name)
    (directory/"node_modules").symlink_to(WORKER/"node_modules",target_is_directory=True)
    base=f"http://127.0.0.1:{args.port}"
    config={"name":"norulo-production-recurring-native-local-only","main":"src/entry.py",
        "compatibility_date":"2026-09-23","compatibility_flags":["python_workers"],
        "workers_dev":False,"preview_urls":False,"routes":[],
        "triggers":{"crons":[production_cron]},
        "vars":{"NORULO_MODE":"production","NORULO_D1_ACCESS_ENABLED":"1",
            "NORULO_RECURRING_EXPENSES_ENABLED":"1","NORULO_PREVIEW_PRODUCT_ENABLED":"0",
            "NORULO_APP_URL":"https://norulo.com","NORULO_ALLOWED_ORIGINS":base,
            "NORULO_EMAIL_AUTH_ENABLED":"0","NORULO_JEV_SUGGESTIONS_ENABLED":"0","NORULO_JEV_SUGGESTIONS_EVALUATED":"0"},
        "d1_databases":[{"binding":"DB","database_name":"production-recurring-native-local-only",
            "database_id":"00000000-0000-0000-0000-000000000046","remote":False,
            "migrations_dir":str(WORKER/"migrations")}],
        "durable_objects":{"bindings":[{"name":"RECURRING_SCHEDULER","class_name":"RecurringScheduler"}]},
        "migrations":[{"tag":"local-recurring-fixture-v1","new_sqlite_classes":["RecurringScheduler"]}]}
    config_path=directory/"wrangler.jsonc"; config_path.write_text(json.dumps(config,indent=2)+"\n")
    bundle=Path("/workspace/.cache/norulo-pyodide/pyodide_314.0.6_2026-08-17_6.capnp.bin")
    if not bundle.is_file() or parity.sha256(bundle)!=parity.BUNDLE_SHA256:
        raise SystemExit("Official pinned Workerd Python cache missing or invalid")
    binary=WORKER/"node_modules/@cloudflare/workerd-linux-64/bin/workerd"
    workerd_package=json.loads((binary.parents[1]/"package.json").read_text())
    if (workerd_package.get("version")!=PINNED_WORKERD_VERSION
            or parity.sha256(binary)!=PINNED_WORKERD_SHA256):
        raise SystemExit("Pinned Workerd version or previously verified binary checksum mismatched")
    wrapper=directory/"workerd-local-cache.sh"
    wrapper.write_text("#!/bin/sh\nexec "+shlex.quote(str(binary))+' "$@" --pyodide-bundle-disk-cache-dir=/workspace/.cache/norulo-pyodide\n'); wrapper.chmod(0o700)
    env={key:value for key,value in os.environ.items() if key not in {"CLOUDFLARE_API_TOKEN","TYPESAFE_API_KEY"}}
    env.update({"XDG_CACHE_HOME":"/workspace/.cache","XDG_CONFIG_HOME":"/workspace/.cache/config",
        "UV_CACHE_DIR":"/workspace/.cache/uv","UV_PYTHON_INSTALL_DIR":"/workspace/.cache/python","UV_SYSTEM_CERTS":"true",
        "NPM_CONFIG_CACHE":str(directory/"npm-cache"),"WRANGLER_SEND_METRICS":"false","CI":"1",
        "MINIFLARE_WORKERD_PATH":str(wrapper),"WRANGLER_LOG_PATH":str(directory/"wrangler-debug.log")})
    files=sorted((source/"norulo_server").glob("*.py"))
    manifest=[(str(path.relative_to(source)),parity.sha256(path)) for path in files]
    evidence={"passed":False,"date":"2026-10-11","recordingTimezone":"Asia/Shanghai","localOnly":True,
        "nativePythonFFI":True,"nativeDurableObjectSQLite":True,"canonicalDefaultAndRecurringScheduler":True,
        "productionModeLocalBinding":True,"productionCron":production_cron,
        "cronTimezone":"UTC","displayCronTimezone":"Asia/Shanghai","displayCronTime":"00:10 daily",
        "localFixtureOnlyExtraHourTicks":True,"realCronInvocationClaimed":False,"singletonScope":"norulo-production-recurring-v1","fixtureClockStart":FIXTURE_NOW,
        "fixtureClockAdvanceSeconds":[86400,3600,3600],"expectedSchemaVersion":12,
        "canonicalApplicationEntrySha256":parity.sha256(source/"application_entry.py"),
        "canonicalSourceTreeSha256":hashlib.sha256(json.dumps(manifest,separators=(",",":")).encode()).hexdigest(),
        "canonicalSourceFileCount":len(files),"sourceSha256":dict(manifest),
        "canonicalRootSourceFileSha256":{path.name:parity.sha256(path) for path in canonical_files},
        "packagedNamespaceVerified":True,"packagedSourceModuleCount":len(files)-1,
        "packagedInitializerSha256":parity.sha256(source/"norulo_server/__init__.py"),"fixtureEntrySha256":parity.sha256(source/"entry.py"),
        "localWorkerConfigSha256":parity.sha256(config_path),
        "localMigrationSetup":{"canonicalMigrationFileSha256":{path.name:parity.sha256(path) for path in sorted((WORKER/"migrations").glob("*.sql"))},
            "migrationCount":12,"localOnly":True,"localCliReportedNativeMetadata":False,"includedInNativeTotals":False},
        "cachedTzdataFileManifestSha256":hashlib.sha256(json.dumps(package_manifest,separators=(",",":")).encode()).hexdigest(),
        "dependencySha256":{name:parity.sha256(directory/name) for name in dependencies},
        "runtimeProvenance":{"workerdSha256":parity.sha256(binary),"workerdVersion":PINNED_WORKERD_VERSION,
            "runtimeBundleSha256":parity.BUNDLE_SHA256,
            "miniflareD1SourceSha256":parity.sha256(WORKER/"node_modules/miniflare/dist/src/workers/d1/database.worker.js")},
        "nativeD1AndCommercialPlanAdapter":True,"providerAcceptanceClaimed":False,"validationBudgetBinding":False,
        "syntheticLocalFreeOwners":1,"syntheticLocalSessions":1,"maximumLocalRules":1,
        "remoteD1Operations":0,"remoteApplicationRequests":0,"realProviderRequests":0,"clientRetries":0,
        "localHttpCap":HTTP_CAP,"finiteLocalNativeRowCaps":{"rowsRead":READ_CAP,"rowsWritten":WRITE_CAP},
        "scope":"Real LOCAL daily-production coordinator and financial posting. Extra hour ticks and unknown-marker injection are private local fixture seams; no actual remote cron invocation is claimed. Native totals exclude the distinct twelve-file LOCAL CLI migration setup. Remote scheduling/provider acceptance remains separate."}
    process,attempted,cases,starts=None,0,[],0
    log_path=directory/"runtime.log"
    cli=["node",str(WORKER/"node_modules/wrangler/bin/wrangler.js")]
    def start(log):
        nonlocal starts
        starts+=1
        process=subprocess.Popen([*cli,"dev","--local","--config",str(config_path),"--ip","127.0.0.1","--port",str(args.port),
            "--inspector-port",str(args.port+1000),"--persist-to",str(directory/"state")],cwd=directory,env=env,
            stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        deadline=time.monotonic()+120
        marker=f"Ready on http://127.0.0.1:{args.port}"
        while time.monotonic()<deadline:
            if process.poll() is not None: raise AssertionError("Native production scheduler startup failed")
            if log_path.read_text(errors="replace").count(marker)>=starts:
                try:
                    with socket.create_connection(("127.0.0.1",args.port),timeout=.2): return process
                except OSError: pass
            time.sleep(.2)
        stop(process)
        raise AssertionError("Native production scheduler startup timed out")
    try:
        with (directory/"migration.log").open("w") as migrations:
            completed=subprocess.run([*cli,"d1","migrations","apply","DB","--local","--config",str(config_path),
                "--persist-to",str(directory/"state")],cwd=directory,env=env,stdout=migrations,stderr=subprocess.STDOUT,timeout=120)
            assert completed.returncode==0,"LOCAL canonical migration application failed"
        with log_path.open("a") as log:
            process=start(log)
            opener=build_opener(ProxyHandler({}),NoRedirect())
            def call(name,path,*,body=None,expected=200,cookie=False):
                nonlocal attempted
                attempted+=1; assert attempted<=HTTP_CAP
                headers={"X-Native-Fixture-Call":str(attempted),"Content-Type":"application/json"}
                if cookie: headers.update({"Cookie":"nr_session=production-recurring-native-owner","Origin":base,"Idempotency-Key":"production-recurring-native-rule"})
                request=Request(base+path,method="POST" if body is not None else "GET",headers=headers,
                    data=json.dumps(body,separators=(",",":")).encode() if body is not None else None)
                try: response=opener.open(request,timeout=30)
                except HTTPError as error: response=error
                with response:
                    payload=json.loads(response.read())
                    cases.append({"name":name,"path":path,"status":response.status,"result":payload})
                    assert response.status==expected,(name,response.status)
                    return payload
            call("setup","/_fixture/setup",body={})
            call("idle_with_expired_activity","/_fixture/tick",body={})
            call("same_hour_empty_replay","/_fixture/tick",body={})
            created=call("future_rule_create","/api/v1/expense-recurring-rules",cookie=True,expected=201,
                body={"target":{"kind":"shared"},"categoryId":"cat_production_recurring","amount":"12.34","currency":"USD",
                    "purpose":"Synthetic native hosting","schedule":{"frequency":"monthly","day":12,"timezone":"UTC","startOn":"2026-10-12"}})
            assert created["nextOccurrenceOn"]=="2026-10-12" and not created["pendingOccurrences"]
            call("same_hour_after_rule_creation","/_fixture/tick",body={})
            call("advance_to_due_day","/_fixture/advance-clock",body={})
            call("before_due","/_fixture/probe")
            call("due_shared_rule","/_fixture/tick",body={})
            call("same_hour_due_replay","/_fixture/tick",body={})
            stop(process); process=start(log)
            call("cold_restart_same_hour","/_fixture/tick",body={})
            call("advance_future_hour","/_fixture/advance-clock",body={})
            call("idle_future_hour","/_fixture/tick",body={})
            call("park_unknown_marker","/_fixture/park-unknown",body={})
            stop(process); process=start(log)
            call("cold_restart_unknown_stopped","/_fixture/tick",body={},expected=503)
            call("unknown_replay_stopped","/_fixture/tick",body={},expected=503)
            call("final","/_fixture/final")
        evidence["passed"]=True
    except Exception as error:
        evidence["failure"]={"type":type(error).__name__,"detail":str(error)[:240]}
    finally:
        stop(process)
        groups=[]
        for line in log_path.read_text(errors="replace").splitlines() if log_path.exists() else []:
            if line.startswith('{"productionRecurringNativeMeta":'):
                groups.append(json.loads(line)["productionRecurringNativeMeta"])
        evidence.update(localHttpRequestsAttempted=attempted,localHttpRequestsCompleted=len(cases),cases=cases,
            runtimeIncarnations=starts,runtimeStopped=process is None or process.poll() is not None,
            nativeStatements=sum(group["statements"] for group in groups),
            nativeRowsRead=sum(group["rowsRead"] for group in groups),nativeRowsWritten=sum(group["rowsWritten"] for group in groups),
            nativeGroups=groups,nativeAttemptsFabricated=False,
            nativeAttemptsObserved=sorted({part["nativeAttempts"] for group in groups for part in group["statementMetadata"]},key=str))
        if evidence["passed"]:
            try:
                verify(cases,groups)
                evidence["acceptance"]={"idleNoD1Writes":True,"idleExpiredActivityUntouched":True,"sameHourNoD1Work":True,
                    "actualSharedExpenseAuditOccurrenceAndOwnerQuota":True,"coldRestartCompletedHourNoD1Work":True,
                    "futureHourNoD1Writes":True,"unknownMarkerColdRestartFailsClosed":True,
                    "rpcStrictBooleanSuccess":True,"canonicalSchemaAndTwelveMigrationNames":True,"schedulerMetricsMatchRawMetadata":True}
            except Exception as error:
                evidence["passed"]=False
                evidence["failure"]={"type":type(error).__name__,"detail":str(error)[:240]}
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(evidence,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({key:evidence[key] for key in ("passed","localOnly","localHttpRequestsCompleted","nativeStatements","nativeRowsRead","nativeRowsWritten","runtimeStopped")},sort_keys=True))
    return 0 if evidence["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

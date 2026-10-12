"""Finite LOCAL native recurrence throughput proof; no remote/provider side effects.

The application and production schedulers are copied unchanged. Synthetic Free
Owners each create five future shared rules through the real HTTP application,
then the real daily scheduler posts one occurrence per rule. Commercial policy
is unchanged. The Cloudflare deployment capacity prerequisite is Workers Paid;
Free here identifies the application's Owner entitlement, not the platform plan.
"""
from __future__ import annotations

import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
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

ROOT=Path(__file__).resolve().parents[1]
WORKER=ROOT/"cloudflare/server"
FIXTURE_START=1791735000  # Synthetic 2026-10-11 16:10:00 UTC.
FIXTURE_DUE=FIXTURE_START+86400
PAID_D1_QUERY_LIMIT=1000
OWNER_RULE_COUNT=5
PINNED_WORKERD_VERSION="1.20260921.1"
PINNED_WORKERD_SHA256="eb449c84ddd55ea357dc73e6c1b50bd255ccdc5d1875544c162435b7bd6168b6"
spec=importlib.util.spec_from_file_location("native_recurring_deps",ROOT/"scripts/check-rest-parity-native-runtime.py")
parity=importlib.util.module_from_spec(spec)
spec.loader.exec_module(parity)

COMMON_ENTRY=r'''
import asyncio
from contextvars import ContextVar
import hashlib
import json
from types import SimpleNamespace
from urllib.parse import urlsplit
from js import Date
import time as system_time
from workers import Response, Request
import application_entry as canonical
from norulo_server.cloudflare_native_d1 import NativeD1
from norulo_server.cloudflare_validation_budget import _field
from norulo_server.cloudflare_d1_mapping import initialize_account
from norulo_server.cloudflare_state_records import record_name, encode_record
import norulo_server.cloudflare_recurring_scheduler as recurring_core
from norulo_server.cloudflare_recurring_scheduler import (PRODUCTION_RECURRING_CRON,
    RECURRING_SCHEDULER_SCOPE, RecurringJournal, DispatchJournal, require_role, owner_scope)
FIXTURE_START=1791735000
FIXTURE_DUE=FIXTURE_START+86400
context=ContextVar("native_recurring_load_context",default={"phase":"unclassified"})
provider_calls=[]
class FixtureClock:
    now=FIXTURE_START
    @classmethod
    def time(cls): return context.get().get("clock",cls.now)
    @classmethod
    def monotonic(cls): return system_time.monotonic()
canonical.time=FixtureClock
recurring_core.time=FixtureClock
class ForbiddenGateway:
    def __init__(self,env): pass
    def __getattr__(self,name):
        async def blocked(*args,**kwargs):
            provider_calls.append(name)
            raise AssertionError("Real providers excluded from finite LOCAL recurrence proof")
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
    def __init__(self,binding):
        super().__init__(binding)
        self.observation=context.get()
    def prepare(self,sql): return ObservedStatement(self,super().prepare(sql))
    async def batch(self,statements):
        statements=list(statements)
        assert 0<len(statements)<=64 and all(item.owner is self for item in statements)
        obs=self.observation
        if obs.get("delayMs") and not obs.get("delayed"):
            obs["delayed"]=True
            print(json.dumps({"recurringLoadInjectedWait":{"rpcId":obs["rpcId"],"milliseconds":obs["delayMs"]}}))
            await asyncio.sleep(obs["delayMs"]/1000)
        result=list(await super().batch([item.native for item in statements]))
        assert len(result)==len(statements)
        metadata=[]
        for part in result:
            meta=_field(part,"meta")
            reads,writes=_field(meta,"rows_read"),_field(meta,"rows_written")
            assert _field(part,"success") is True and type(reads) is int and type(writes) is int
            assert reads>=0 and writes>=0
            metadata.append({"rowsRead":reads,"rowsWritten":writes,"nativeAttempts":_field(meta,"total_attempts")})
        print(json.dumps({"recurringLoadNativeMeta":{"phase":obs["phase"],"rpcId":obs.get("rpcId"),"owner":obs.get("owner"),
            "statements":len(result),"rowsRead":sum(item["rowsRead"] for item in metadata),
            "rowsWritten":sum(item["rowsWritten"] for item in metadata),"statementMetadata":metadata}}))
        return result
canonical.NativeD1=ObservedNativeD1
async def commands(native,values):
    return await native.batch([native.prepare(sql).bind(*params) for sql,params in values])
def owner_id(index): return "usr_github_"+str(798000000+index)
def seed_owner(index):
    identity=owner_id(index)
    user={"id":identity,"name":"Synthetic native load Owner "+str(index),
        "createdAt":FIXTURE_START-1000,"billing":{"plan":"free"}}
    payload=encode_record("users",identity,user)
    session="recurring-load-local-"+str(index)
    return [("INSERT INTO app_state(name,payload,updated_at) VALUES(?,?,?)",(record_name("users",identity),payload,FIXTURE_START)),
        ("INSERT INTO app_state(name,payload,updated_at) VALUES(?,?,?)",(record_name("sessions",session),
            encode_record("sessions",session,{"id":session,"userId":identity,"expiresAt":FIXTURE_START+5*86400}),FIXTURE_START)),
        *initialize_account(owner_id=identity,account_snapshot=payload,now=FIXTURE_START),
        ("INSERT INTO expense_categories(id,owner_id,name,revision,created_at,updated_at) VALUES(?,?,'Hosting',1,'local','local')",
            ("cat_load_"+str(index),identity))]
PROBE_SQL=(
    "SELECT owner_id,COUNT(*) records,SUM(amount_minor) amountMinor,COUNT(DISTINCT currency) currencies FROM expenses WHERE deleted_at IS NULL GROUP BY owner_id ORDER BY owner_id",
    "SELECT owner_id,COUNT(*) total FROM expense_events WHERE actor_kind='schedule' GROUP BY owner_id ORDER BY owner_id",
    """SELECT o.owner_id,COUNT(*) total FROM expense_recurring_occurrences o
        JOIN expense_recurring_rules r ON r.id=o.rule_id AND r.owner_id=o.owner_id
        JOIN expenses e ON e.id=o.expense_id AND e.owner_id=o.owner_id
        WHERE o.period_key='M2026-10' AND o.scheduled_on='2026-10-12'
        AND e.occurred_on=o.scheduled_on AND e.amount_minor=1234 AND e.currency='USD'
        AND e.target_kind='shared' AND e.project_id IS NULL AND e.deleted_at IS NULL
        AND r.actor_user_id=r.owner_id AND r.next_occurrence_on='2026-11-12' AND r.revision=2
        GROUP BY o.owner_id ORDER BY o.owner_id""",
    "SELECT owner_id,records,writes,minute_writes,month,jev_reserved_microusd,record_cap,minute_cap,month_cap FROM ledger_plan_usage ORDER BY owner_id",
    "SELECT owner_id,plan,dirty FROM account_entitlement_authority ORDER BY owner_id",
    "SELECT COUNT(*) total FROM expense_recurring_rules WHERE status='active' AND revision=1 AND next_occurrence_on='2026-10-12'",
    "SELECT COUNT(*) total FROM expense_recurring_rules WHERE status='active' AND revision=2 AND next_occurrence_on='2026-11-12'",
    "SELECT COUNT(*) total FROM expense_recurring_pending",
    "SELECT COUNT(*) total FROM d1_command_guard",
    "SELECT name FROM d1_migrations ORDER BY id LIMIT 14",
    """SELECT COUNT(*) total FROM expense_events a JOIN expenses e ON e.id=a.expense_id
        JOIN expense_recurring_occurrences o ON o.expense_id=e.id
        WHERE a.owner_id=e.owner_id AND o.owner_id=e.owner_id AND a.actor_kind='schedule'
        AND a.actor_id=o.rule_id||':'||e.owner_id AND e.category_id='cat_load_'||CAST(CAST(SUBSTR(e.owner_id,12) AS INTEGER)-798000000 AS TEXT)""",
)
async def integrity(env):
    token=context.set({"phase":"integrity-probe"})
    try:
        parts=await commands(ObservedNativeD1(env.DB),[(sql,()) for sql in PROBE_SQL])
        result=[[dict(row) for row in _field(part,"results",[])] for part in parts]
        assert not provider_calls
        return {"expenses":result[0],"events":result[1],"occurrences":result[2],"usage":result[3],"authority":result[4],
            "unprocessedRules":result[5][0]["total"],"completedPeriodRules":result[6][0]["total"],"pending":result[7][0]["total"],
            "commandGuards":result[8][0]["total"],"migrationNames":[row["name"] for row in result[9]],
            "linkedFinancialChains":result[10][0]["total"],"providerCalls":0}
    finally: context.reset(token)
'''


FIXTURE_ENTRY=r'''
class Default(canonical.Default):
    async def fetch(self,request):
        raw=await request.bytes()
        raw=raw if isinstance(raw,bytes) else raw.to_bytes()
        assert len(raw)<=8192
        request=Request(str(request.url),method=str(request.method),headers=dict(request.headers.items()),body=raw if raw else None)
        path=urlsplit(str(request.url)).path
        namespace=self.env.RECURRING_SCHEDULER
        stub=namespace.get(namespace.idFromName(RECURRING_SCHEDULER_SCOPE))
        if path=="/_fixture/tick":
            status,code=200,None
            try:
                await super().scheduled(SimpleNamespace(cron=PRODUCTION_RECURRING_CRON,
                    scheduledTime=float(FIXTURE_DUE*1000)),self.env,self.ctx)
            except RuntimeError as error:
                assert str(error)=="RECURRING_EXECUTION_UNAVAILABLE"
                status,code=503,str(error)
            response=await stub.fetch(Request(str(request.url).replace('/_fixture/tick','/_fixture/status'),method="GET"))
            body=json.loads(await response.text())
            body["canonicalDefaultScheduledCompleted"]=status==200
            body["strictBooleanRpcSuccessAccepted"]=status==200
            if code:body["defaultFailureCode"]=code
            return Response.json(body,status=status)
        if path.startswith("/_fixture/"): return await stub.fetch(request)
        token=context.set({"phase":"application","clock":FIXTURE_START})
        try:return await super().fetch(request)
        finally:context.reset(token)

class RecurringScheduler(canonical.RecurringScheduler):
    async def runRecurring(self):
        clock=int(await self.ctx.storage.get("fixtureNow") or FIXTURE_START)
        rpc_id="root:"+str(Date.now())
        token=context.set({"phase":"root-scheduler","clock":clock,"rpcId":rpc_id})
        print(json.dumps({"recurringLoadRootRpc":{"state":"start","rpcId":rpc_id,"clock":clock}}))
        try:
            result=await super().runRecurring()
            await self.ctx.storage.put("fixtureRootResult",json.dumps(result,separators=(",",":")))
            await self.ctx.storage.put("fixtureRootRpcId",rpc_id)
            return result
        finally:
            print(json.dumps({"recurringLoadRootRpc":{"state":"finish","rpcId":rpc_id,"clock":clock}}))
            context.reset(token)
    async def runOwnerChunk(self,owner_id,epoch,expected_chunk):
        calls=getattr(self,"_fixtureOwnerCalls",0)+1
        self._fixtureOwnerCalls=calls
        rpc_id=str(owner_id)+":"+str(int(epoch))+":"+str(int(expected_chunk))+":"+str(Date.now())+":"+str(calls)
        obs={"phase":"owner-scheduler","clock":int(epoch),"owner":str(owner_id),"rpcId":rpc_id,
            "delayMs":int(getattr(self.env,"NATIVE_LOAD_DELAY_MS","0")),"delayed":False}
        token=context.set(obs)
        print(json.dumps({"recurringLoadOwnerRpc":{"state":"start","rpcId":rpc_id,"owner":str(owner_id),
            "expectedChunk":int(expected_chunk),"wallClockMilliseconds":Date.now()}}))
        self._fixtureLastOwnerRpcId=rpc_id
        try:
            result=await super().runOwnerChunk(owner_id,epoch,expected_chunk)
            print(json.dumps({"recurringLoadOwnerResult":{"rpcId":rpc_id,"result":result}}))
            return result
        finally:
            print(json.dumps({"recurringLoadOwnerRpc":{"state":"finish","rpcId":rpc_id,"owner":str(owner_id),
                "wallClockMilliseconds":Date.now()}}))
            context.reset(token)
    async def fixtureParkOwnerActive(self):
        owner=owner_id(0)
        require_role(self.ctx,self.env,owner)
        journal=DispatchJournal(self.ctx.storage.sql,owner_scope(owner))
        state=journal.read()
        assert state["state"]=="complete" and state["owner"]==owner
        state["state"]="active"
        journal.write(state)
        return {"parked":True,"owner":owner,"state":"active","scope":owner_scope(owner)}
    async def fixtureOwnerState(self):
        owner=owner_id(0)
        require_role(self.ctx,self.env,owner)
        state=DispatchJournal(self.ctx.storage.sql,owner_scope(owner)).read()
        return {"owner":owner,"state":state["state"],"epoch":state["epoch"],"scope":owner_scope(owner),
            "rpcId":getattr(self,"_fixtureLastOwnerRpcId",None)}
    async def ownerProgress(self,owner_id,epoch):
        token=context.set({"phase":"owner-progress","clock":int(epoch),"owner":str(owner_id)})
        try:return await super().ownerProgress(owner_id,epoch)
        finally:context.reset(token)
    async def fetch(self,request):
        path=urlsplit(str(request.url)).path
        if not path.startswith("/_fixture/"):return await super().fetch(request)
        require_role(self.ctx,self.env)
        legacy=RecurringJournal(self.ctx.storage.sql)
        if path in {"/_fixture/park-owner-unknown","/_fixture/owner-unknown-next-day"}:
            owner=owner_id(0)
            namespace=self.env.RECURRING_SCHEDULER
            stub=namespace.get(namespace.idFromName(owner_scope(owner)))
            if path=="/_fixture/park-owner-unknown":return Response.json(await stub.fixtureParkOwnerActive())
            result=await stub.runOwnerChunk(owner,float(FIXTURE_DUE+86400),0.0)
            return Response.json({"ownerResult":result,"ownerState":await stub.fixtureOwnerState(),
                "manualOwnerMarkerFixture":True})
        if path=="/_fixture/setup":
            assert await self.ctx.storage.get("fixtureNow") is None
            owners=int(getattr(self.env,"NATIVE_LOAD_OWNER_COUNT"))
            assert 0<owners<=600
            token=context.set({"phase":"fixture-setup","clock":FIXTURE_START})
            try:
                native=ObservedNativeD1(self.env.DB)
                for index in range(owners):await commands(native,seed_owner(index))
            finally:context.reset(token)
            await self.ctx.storage.put("fixtureNow",float(FIXTURE_START))
        elif path=="/_fixture/advance-clock":
            assert int(await self.ctx.storage.get("fixtureNow"))==FIXTURE_START
            await self.ctx.storage.put("fixtureNow",float(FIXTURE_DUE))
        elif path=="/_fixture/park-unknown":
            assert legacy.snapshot()["state"]=="idle"
            unknown=FIXTURE_DUE+86400
            assert legacy.begin(unknown//3600) is True
            await self.ctx.storage.put("fixtureNow",float(unknown))
        elif path not in {"/_fixture/probe","/_fixture/status"}:
            return await super().fetch(request)
        result=await self.ctx.storage.get("fixtureRootResult")
        value={"rootResult":json.loads(str(result)) if result else None,"legacyJournal":legacy.snapshot(),
            "fixtureClock":int(await self.ctx.storage.get("fixtureNow") or FIXTURE_START),"productionCron":PRODUCTION_RECURRING_CRON,
            "rootRpcId":str(await self.ctx.storage.get("fixtureRootRpcId") or "")}
        if path!="/_fixture/status":value["integrity"]=await integrity(self.env)
        return Response.json(value)

class EmailAdmission(canonical.EmailAdmission):pass
'''


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args): return None


def stop(process):
    if process is not None and process.poll() is None:
        os.killpg(process.pid,signal.SIGTERM)
        try: process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=5)


def canonical_constants():
    nodes=ast.parse((ROOT/"norulo_server/cloudflare_recurring_scheduler.py").read_text()).body
    values={}
    for node in nodes:
        if isinstance(node,ast.Assign):
            for target in node.targets:
                if isinstance(target,ast.Name):
                    try: values[target.id]=ast.literal_eval(node.value)
                    except (ValueError,TypeError): pass
    return values


def verify_financial_snapshot(value,owners,rules_per_owner):
    expected={"usr_github_"+str(798000000+index) for index in range(owners)}
    for name in ("expenses","events","occurrences","usage","authority"):
        assert {row["owner_id"] for row in value[name]}==expected,name
    assert all(row["records"]==rules_per_owner and row["amountMinor"]==rules_per_owner*1234 and row["currencies"]==1 for row in value["expenses"])
    assert all(row["total"]==rules_per_owner for row in value["events"]+value["occurrences"])
    assert all(row["records"]==rules_per_owner and row["writes"]==2*rules_per_owner
        and row["minute_writes"]==rules_per_owner and row["month"]=="2026-10" and row["jev_reserved_microusd"]==0
        and row["record_cap"]==100 and row["minute_cap"]==10 and row["month_cap"]==1000 for row in value["usage"])
    assert all(row["plan"]=="free" and row["dirty"]==0 for row in value["authority"])
    assert value["completedPeriodRules"]==value["linkedFinancialChains"]==owners*rules_per_owner
    assert value["unprocessedRules"]==value["pending"]==value["commandGuards"]==value["providerCalls"]==0
    assert len(value["migrationNames"])==12


def parse_native_log(log_path,owner_sql_cap,parallelism):
    groups,events,waits,root_events,owner_results=[],[],[],[],[]
    active_root=None
    for line in log_path.read_text(errors="replace").splitlines():
        if line.startswith('{"recurringLoadRootRpc":'):
            event=json.loads(line)["recurringLoadRootRpc"]
            root_events.append(event)
            if event["state"]=="start":
                assert active_root is None
                active_root=event["rpcId"]
            else:
                assert active_root==event["rpcId"]
                active_root=None
        elif line.startswith('{"recurringLoadNativeMeta":'):
            group=json.loads(line)["recurringLoadNativeMeta"]
            group["rootCallId"]=active_root
            groups.append(group)
        elif line.startswith('{"recurringLoadOwnerRpc":'):events.append(json.loads(line)["recurringLoadOwnerRpc"])
        elif line.startswith('{"recurringLoadOwnerResult":'):owner_results.append(json.loads(line)["recurringLoadOwnerResult"])
        elif line.startswith('{"recurringLoadInjectedWait":'):waits.append(json.loads(line)["recurringLoadInjectedWait"])
    assert active_root is None
    by_rpc={}
    for group in groups:
        if group["phase"]=="owner-scheduler":
            bucket=by_rpc.setdefault(group["rpcId"],{"owner":group["owner"],"statements":0,"rowsRead":0,"rowsWritten":0})
            for name in ("statements","rowsRead","rowsWritten"):bucket[name]+=group[name]
    for captured in owner_results:
        raw=by_rpc.get(captured["rpcId"],{"statements":0,"rowsRead":0,"rowsWritten":0})
        metrics=captured["result"].get("metrics")
        if metrics:
            assert metrics["operations"]==raw["statements"] and metrics["rowsRead"]==raw["rowsRead"] and metrics["rowsWritten"]==raw["rowsWritten"]
        else:assert raw["statements"]==0
    root_metadata={}
    for group in groups:
        if group["phase"]=="root-scheduler":
            bucket=root_metadata.setdefault(group["rpcId"],{"statements":0,"rowsRead":0,"rowsWritten":0})
            for key in ("statements","rowsRead","rowsWritten"):bucket[key]+=group[key]
    assert all(value["statements"]<=PAID_D1_QUERY_LIMIT for value in root_metadata.values())
    active,peak=0,0
    for event in events:
        active+=1 if event["state"]=="start" else -1
        assert active>=0
        peak=max(peak,active)
    assert active==0
    assert 0<owner_sql_cap<=PAID_D1_QUERY_LIMIT
    assert all(value["statements"]<=owner_sql_cap for value in by_rpc.values())
    assert peak<=parallelism
    return {"nativeGroups":groups,"rootRpcEvents":root_events,"ownerRpcEvents":events,"ownerRpcResults":owner_results,
        "ownerRpcMetadata":by_rpc,"rootRpcMetadata":root_metadata,
        "rootRpcMaximumNativeStatements":max((value["statements"] for value in root_metadata.values()),default=0),
        "observedOwnerRpcPeakConcurrency":peak,"injectedWaits":waits,
        "ownerRpcMaximumNativeStatements":max((value["statements"] for value in by_rpc.values()),default=0),
        "nativeStatements":sum(item["statements"] for item in groups),
        "nativeRowsRead":sum(item["rowsRead"] for item in groups),"nativeRowsWritten":sum(item["rowsWritten"] for item in groups),
        "nativeAttemptsObserved":sorted({part["nativeAttempts"] for item in groups for part in item["statementMetadata"]},key=str)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--occurrences",type=int,choices=(8,1000,3000),required=True)
    parser.add_argument("--port",type=int,default=8947)
    parser.add_argument("--overlap-delay-ms",type=int,choices=(0,1200),default=0)
    parser.add_argument("--tzdata-cache",type=Path)
    args=parser.parse_args()
    if args.overlap_delay_ms and args.occurrences!=8:
        raise SystemExit("Injected overlap wait belongs only to the separate eight-owner profile")
    rules_per_owner=1 if args.occurrences==8 else OWNER_RULE_COUNT
    owners=args.occurrences//rules_per_owner
    constants=canonical_constants()
    required={"PRODUCTION_RECURRING_CRON","OWNER_PARALLELISM","MAX_OWNER_NATIVE_SQL"}
    if not required<=constants.keys():raise SystemExit("Canonical Owner scheduler contract is not ready")
    entry_tree=ast.parse((WORKER/"src/entry.py").read_text())
    coordinator=next(node for node in entry_tree.body if isinstance(node,ast.ClassDef) and node.name=="RecurringScheduler")
    methods={node.name for node in coordinator.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))}
    if not {"runRecurring","runOwnerChunk","ownerProgress"}<=methods:
        raise SystemExit("Canonical Owner scheduler implementation is not ready")
    if constants["PRODUCTION_RECURRING_CRON"]!="10 16 * * *":
        raise SystemExit("Load proof expects the reviewed daily 16:10 UTC cron")
    directory=args.run_dir.resolve()
    if not directory.is_relative_to(Path("/workspace")) or not 1024<=args.port<=64535:
        raise SystemExit("Use a fresh /workspace directory and an unprivileged port")
    directory.mkdir(parents=True,exist_ok=False)
    subprocess.run([os.sys.executable,str(WORKER/"sync_server_modules.py"),"--check"],cwd=ROOT,check=True)
    canonical_files=sorted((ROOT/"norulo_server").glob("*.py"))
    packaged_files=sorted((WORKER/"src/norulo_server").glob("*.py"))
    if {path.name for path in canonical_files}!={path.name for path in packaged_files}:
        raise SystemExit("Canonical and packaged module namespaces differ")
    for path in canonical_files:
        if path.name!="__init__.py" and path.read_bytes()!=(WORKER/"src/norulo_server"/path.name).read_bytes():
            raise SystemExit("Packaged module bytes are stale")
    if (WORKER/"src/norulo_server/__init__.py").read_bytes()!=b"":
        raise SystemExit("Expected the canonical blank packaged initializer")
    source=directory/"src";source.mkdir()
    entry=COMMON_ENTRY+FIXTURE_ENTRY
    (source/"entry.py").write_text(entry)
    shutil.copy2(WORKER/"src/entry.py",source/"application_entry.py")
    shutil.copytree(WORKER/"src/norulo_server",source/"norulo_server",ignore=shutil.ignore_patterns("__pycache__","*.pyc"))
    shutil.copytree(WORKER/"python_modules",directory/"python_modules",ignore=shutil.ignore_patterns("__pycache__","*.pyc"))
    package_root,package_manifest=parity.pinned_tzdata(args.tzdata_cache)
    shutil.copytree(package_root/"tzdata",directory/"python_modules/tzdata",dirs_exist_ok=True,ignore=shutil.ignore_patterns("__pycache__","*.pyc"))
    dependencies=("pyproject.toml","uv.lock","pylock.toml","package.json","package-lock.json")
    for name in dependencies:shutil.copy2(WORKER/name,directory/name)
    (directory/"node_modules").symlink_to(WORKER/"node_modules",target_is_directory=True)
    base=f"http://127.0.0.1:{args.port}"
    config={"name":"norulo-recurring-load-native-local-only","main":"src/entry.py",
        "compatibility_date":"2026-09-23","compatibility_flags":["python_workers"],
        "workers_dev":False,"preview_urls":False,"routes":[],"triggers":{"crons":[constants["PRODUCTION_RECURRING_CRON"]]},
        "vars":{"NORULO_MODE":"production","NORULO_D1_ACCESS_ENABLED":"1","NORULO_RECURRING_EXPENSES_ENABLED":"1",
            "NORULO_PREVIEW_PRODUCT_ENABLED":"0","NORULO_APP_URL":"https://norulo.com","NORULO_ALLOWED_ORIGINS":base,
            "NORULO_EMAIL_AUTH_ENABLED":"0","NORULO_JEV_SUGGESTIONS_ENABLED":"0","NORULO_JEV_SUGGESTIONS_EVALUATED":"0",
            "NATIVE_LOAD_OWNER_COUNT":str(owners),"NATIVE_LOAD_DELAY_MS":str(args.overlap_delay_ms)},
        "d1_databases":[{"binding":"DB","database_name":"recurring-load-native-local-only",
            "database_id":"00000000-0000-0000-0000-000000000047","remote":False,"migrations_dir":str(WORKER/"migrations")}],
        "durable_objects":{"bindings":[{"name":"RECURRING_SCHEDULER","class_name":"RecurringScheduler"}]},
        "migrations":[{"tag":"local-recurring-load-fixture-v1","new_sqlite_classes":["RecurringScheduler"]}]}
    config_path=directory/"wrangler.jsonc";config_path.write_text(json.dumps(config,indent=2)+"\n")
    bundle=Path("/workspace/.cache/norulo-pyodide/pyodide_314.0.6_2026-08-17_6.capnp.bin")
    if not bundle.is_file() or parity.sha256(bundle)!=parity.BUNDLE_SHA256:
        raise SystemExit("Official pinned Python bundle checksum mismatched")
    binary=WORKER/"node_modules/@cloudflare/workerd-linux-64/bin/workerd"
    if json.loads((binary.parents[1]/"package.json").read_text()).get("version")!=PINNED_WORKERD_VERSION or parity.sha256(binary)!=PINNED_WORKERD_SHA256:
        raise SystemExit("Pinned Workerd version/checksum mismatched")
    wrapper=directory/"workerd-local-cache.sh"
    wrapper.write_text("#!/bin/sh\nexec "+shlex.quote(str(binary))+' "$@" --pyodide-bundle-disk-cache-dir=/workspace/.cache/norulo-pyodide\n')
    wrapper.chmod(0o700)
    env={key:value for key,value in os.environ.items() if key not in {"CLOUDFLARE_API_TOKEN","TYPESAFE_API_KEY"}}
    env.update({"XDG_CACHE_HOME":"/workspace/.cache","XDG_CONFIG_HOME":"/workspace/.cache/config",
        "UV_CACHE_DIR":"/workspace/.cache/uv","UV_PYTHON_INSTALL_DIR":"/workspace/.cache/python","UV_SYSTEM_CERTS":"true",
        "NPM_CONFIG_CACHE":str(directory/"npm-cache"),"WRANGLER_SEND_METRICS":"false","CI":"1",
        "MINIFLARE_WORKERD_PATH":str(wrapper),"WRANGLER_LOG_PATH":str(directory/"wrangler-debug.log")})
    manifest=[(str(path.relative_to(source)),parity.sha256(path)) for path in sorted((source/"norulo_server").glob("*.py"))]
    evidence={"passed":False,"date":"2026-10-11","recordingTimezone":"Asia/Shanghai","localOnly":True,
        "expectedOccurrences":args.occurrences,"syntheticLocalFreeOwners":owners,"rulesPerOwner":rules_per_owner,
        "ownerEntitlementPolicyUnchanged":True,"noFabricatedPaidEntitlement":True,
        "platformCapacityPrerequisite":"Cloudflare Workers Paid; not proved by local application Free entitlement",
        "platformPaidD1QueryCeiling":PAID_D1_QUERY_LIMIT,"canonicalSchedulerConstants":constants,
        "productionCron":constants["PRODUCTION_RECURRING_CRON"],"realCronInvocationClaimed":False,
        "injectedFirstNativeAwaitDelayMs":args.overlap_delay_ms,"productionLatencyClaimed":False,
        "fixtureClockStart":FIXTURE_START,"fixtureClockDue":FIXTURE_DUE,
        "canonicalApplicationEntrySha256":parity.sha256(source/"application_entry.py"),
        "canonicalSourceTreeSha256":hashlib.sha256(json.dumps(manifest,separators=(",",":")).encode()).hexdigest(),
        "sourceSha256":dict(manifest),"canonicalRootSourceFileSha256":{path.name:parity.sha256(path) for path in canonical_files},
        "packagedNamespaceVerified":True,"packagedSourceModuleCount":len(manifest)-1,
        "fixtureEntrySha256":parity.sha256(source/"entry.py"),"localWorkerConfigSha256":parity.sha256(config_path),
        "dependencySha256":{name:parity.sha256(directory/name) for name in dependencies},
        "tzdataManifestSha256":hashlib.sha256(json.dumps(package_manifest,separators=(",",":")).encode()).hexdigest(),
        "runtimeProvenance":{"workerdVersion":PINNED_WORKERD_VERSION,"workerdSha256":PINNED_WORKERD_SHA256,
            "pythonBundleSha256":parity.BUNDLE_SHA256,"miniflareD1SourceSha256":parity.sha256(WORKER/"node_modules/miniflare/dist/src/workers/d1/database.worker.js")},
        "localMigrationSetup":{"files":{path.name:parity.sha256(path) for path in sorted((WORKER/"migrations").glob("*.sql"))},
            "localOnly":True,"includedInNativeTotals":False,"localCliReportedNativeMetadata":False},
        "remoteD1Operations":0,"remoteApplicationRequests":0,"realProviderRequests":0,"clientRetries":0,
        "validationBudgetBinding":False,"maximumSetupOwnerParallelism":8,"setupPerOwnerSequential":True}
    process,starts,attempts,cases=None,0,0,[]
    log_path=directory/"runtime.log"
    cli=["node",str(WORKER/"node_modules/wrangler/bin/wrangler.js")]
    def start(log):
        nonlocal starts
        starts+=1
        child=subprocess.Popen([*cli,"dev","--local","--config",str(config_path),"--ip","127.0.0.1","--port",str(args.port),
            "--inspector-port",str(args.port+1000),"--persist-to",str(directory/"state")],cwd=directory,env=env,
            stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        deadline=time.monotonic()+120
        marker=f"Ready on http://127.0.0.1:{args.port}"
        while time.monotonic()<deadline:
            if child.poll() is not None:raise AssertionError("Native load Worker startup failed")
            if log_path.read_text(errors="replace").count(marker)>=starts:
                try:
                    with socket.create_connection(("127.0.0.1",args.port),timeout=.2):return child
                except OSError:pass
            time.sleep(.2)
        stop(child);raise AssertionError("Native load Worker startup timed out")
    def request(path,*,body=None,owner=None,index=None,expected=200,timeout=660):
        headers={"Content-Type":"application/json"}
        if owner is not None:
            headers.update({"Cookie":"nr_session=recurring-load-local-"+str(owner),"Origin":base,
                "Idempotency-Key":"recurring-load-local-"+str(owner)+"-"+str(index)})
        opener=build_opener(ProxyHandler({}),NoRedirect())
        req=Request(base+path,method="POST" if body is not None else "GET",headers=headers,
            data=json.dumps(body,separators=(",",":")).encode() if body is not None else None)
        try:response=opener.open(req,timeout=timeout)
        except HTTPError as error:response=error
        with response:
            result=json.loads(response.read())
            assert response.status==expected,(path,response.status,result.get("error"))
            return result
    def call(name,path,*,body=None,expected=200):
        nonlocal attempts
        attempts+=1
        assert attempts<=16
        begin=time.perf_counter()
        value=request(path,body=body,expected=expected)
        cases.append({"name":name,"path":path,"status":expected,"durationSeconds":time.perf_counter()-begin,"result":value})
        return value
    try:
        with (directory/"migration.log").open("w") as log:
            completed=subprocess.run([*cli,"d1","migrations","apply","DB","--local","--config",str(config_path),
                "--persist-to",str(directory/"state")],cwd=directory,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=120)
            assert completed.returncode==0,"LOCAL migration setup failed"
        with log_path.open("a") as log:
            process=start(log)
            call("setup","/_fixture/setup",body={})
            idle=call("idle_before_rules","/_fixture/tick",body={})
            assert idle["strictBooleanRpcSuccessAccepted"] and idle["rootResult"]["ok"] is True
            setup_begin=time.perf_counter()
            def create_owner_rules(owner):
                for index in range(rules_per_owner):
                    result=request("/api/v1/expense-recurring-rules",owner=owner,index=index,expected=201,
                        body={"target":{"kind":"shared"},"categoryId":"cat_load_"+str(owner),"amount":"12.34","currency":"USD",
                            "purpose":"Synthetic native load "+str(index),
                            "schedule":{"frequency":"monthly","day":12,"timezone":"UTC","startOn":"2026-10-12"}})
                    assert result["nextOccurrenceOn"]=="2026-10-12" and not result["pendingOccurrences"]
                return rules_per_owner
            with ThreadPoolExecutor(max_workers=8) as pool:created=sum(pool.map(create_owner_rules,range(owners)))
            evidence["localHttpRulesCreated"]=created
            evidence["httpRuleCreationWallSeconds"]=time.perf_counter()-setup_begin
            assert created==args.occurrences
            before=call("before_due","/_fixture/probe")
            assert before["integrity"]["unprocessedRules"]==args.occurrences and not before["integrity"]["expenses"]
            assert all(row["writes"]==rules_per_owner and row["records"]==0 for row in before["integrity"]["usage"])
            call("advance_to_due","/_fixture/advance-clock",body={})
            due=call("due_daily_pass","/_fixture/tick",body={})
            assert due["strictBooleanRpcSuccessAccepted"] and due["rootResult"]["ok"] is True
            assert due["rootResult"]["created"]==args.occurrences and due["rootResult"]["selectedOwners"]==owners
            assert due["rootResult"]["failedOwners"]==0 and due["rootResult"]["backlog"] is False
            after=call("after_due","/_fixture/probe")
            verify_financial_snapshot(after["integrity"],owners,rules_per_owner)
            replay=call("same_epoch_replay","/_fixture/tick",body={})
            assert replay["strictBooleanRpcSuccessAccepted"]
            stop(process);process=start(log)
            cold=call("cold_restart_replay","/_fixture/tick",body={})
            assert cold["strictBooleanRpcSuccessAccepted"]
            unchanged=call("after_replays","/_fixture/probe")
            assert unchanged["integrity"]==after["integrity"]
            call("park_owner_unknown","/_fixture/park-owner-unknown",body={})
            warm_owner=call("owner_unknown_next_day","/_fixture/owner-unknown-next-day",body={})
            assert warm_owner["ownerResult"]["ok"] is False and warm_owner["ownerResult"]["error"]=="RECURRING_OUTCOME_UNKNOWN"
            assert warm_owner["ownerState"]["state"]=="active"
            stop(process);process=start(log)
            cold_owner=call("owner_unknown_cold_restart","/_fixture/owner-unknown-next-day",body={})
            assert cold_owner["ownerResult"]["ok"] is False and cold_owner["ownerResult"]["error"]=="RECURRING_OUTCOME_UNKNOWN"
            assert cold_owner["ownerState"]["state"]=="active"
            owner_unchanged=call("after_owner_unknown","/_fixture/probe")
            assert owner_unchanged["integrity"]==after["integrity"]
            call("park_unknown","/_fixture/park-unknown",body={})
            stop(process);process=start(log)
            unknown=call("unknown_cold_restart","/_fixture/tick",body={},expected=503)
            assert unknown["rootResult"]["ok"] is False and unknown["legacyJournal"]["state"]=="active"
            final=call("final","/_fixture/probe")
            assert final["integrity"]==after["integrity"]
        evidence["passed"]=True
    except Exception as error:
        evidence["failure"]={"type":type(error).__name__,"detail":str(error)[:240]}
    finally:
        stop(process)
        if log_path.exists():
            try:evidence.update(parse_native_log(log_path,constants["MAX_OWNER_NATIVE_SQL"],constants["OWNER_PARALLELISM"]))
            except Exception as error:
                evidence["passed"]=False
                evidence["metadataFailure"]={"type":type(error).__name__,"detail":str(error)[:240]}
        evidence.update(cases=cases,localFixtureHttpRequestsAttempted=attempts,runtimeIncarnations=starts,
            runtimeStopped=process is None or process.poll() is not None,nativeAttemptsFabricated=False)
        if evidence["passed"]:
            try:
                by_name={item["name"]:item for item in cases}
                assert 2<=evidence["observedOwnerRpcPeakConcurrency"]<=constants["OWNER_PARALLELISM"]
                assert evidence["ownerRpcMetadata"]
                for name in ("idle_before_rules","same_epoch_replay","cold_restart_replay","unknown_cold_restart"):
                    rpc_id=by_name[name]["result"]["rootRpcId"]
                    selected=[group for group in evidence["nativeGroups"] if group["rootCallId"]==rpc_id]
                    assert sum(group["rowsWritten"] for group in selected)==0,name
                for name in ("owner_unknown_next_day","owner_unknown_cold_restart"):
                    rpc_id=by_name[name]["result"]["ownerState"]["rpcId"]
                    assert all(group["rpcId"]!=rpc_id for group in evidence["nativeGroups"]),name
                due_result=by_name["due_daily_pass"]["result"]
                due_groups=[group for group in evidence["nativeGroups"] if group["rootCallId"]==due_result["rootRpcId"]]
                metrics=due_result["rootResult"]["metrics"]
                assert metrics["complete"] is True
                assert metrics["operations"]==sum(group["statements"] for group in due_groups)
                assert metrics["rowsRead"]==sum(group["rowsRead"] for group in due_groups)
                assert metrics["rowsWritten"]==sum(group["rowsWritten"] for group in due_groups)
                assert all(item["rowsWritten"]==0 for item in evidence["nativeGroups"] if item["phase"]=="integrity-probe")
                if args.overlap_delay_ms:
                    assert evidence["observedOwnerRpcPeakConcurrency"]==constants["OWNER_PARALLELISM"]
                    assert len(evidence["injectedWaits"])==owners
                else:assert not evidence["injectedWaits"]
                evidence["localDailyPassWallSeconds"]=by_name["due_daily_pass"]["durationSeconds"]
                evidence["localOccursPerSecond"]=args.occurrences/evidence["localDailyPassWallSeconds"]
                evidence["acceptance"]={"exactExpenseAuditOccurrenceAndOwnerQuota":True,"boundedNativeOwnerConcurrency":True,
                    "perOwnerRpcBelowConfiguredSqlCapAndPaid1000":True,"sameEpochAndColdRestartNoDuplicateOrD1Writes":True,
                    "unknownLegacyRootMarkerColdRestartFailClosed":True,"unknownOwnerMarkerNextDayAndColdRestartNoD1":True,
                    "nativeRootAndOwnerMetricsMatchRawMetadata":True,"manualUnknownMarkerFixtureNotLostCommitSimulation":True,"nativeSchemaAndJournal":True,
                    "commercialFreePlanLimitsUnchanged":True,"realProviderRequests":0,"remoteD1Operations":0}
            except Exception as error:
                evidence["passed"]=False;evidence["acceptanceFailure"]={"type":type(error).__name__,"detail":str(error)[:240]}
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(evidence,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({key:evidence.get(key) for key in ("passed","expectedOccurrences","localHttpRulesCreated","nativeStatements",
        "nativeRowsRead","nativeRowsWritten","ownerRpcMaximumNativeStatements","rootRpcMaximumNativeStatements","observedOwnerRpcPeakConcurrency","localDailyPassWallSeconds","runtimeStopped")},sort_keys=True))
    return 0 if evidence["passed"] else 1


if __name__=="__main__":
    raise SystemExit(main())

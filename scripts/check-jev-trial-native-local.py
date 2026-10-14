#!/usr/bin/env python3
"""Finite isolated workerd/D1 proof of the canonical Jev admission SQL. No provider or production calls."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import signal
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from norulo_server.cloudflare_plan_limits import _USAGE_SQL
from norulo_server.cloudflare_preview_schema import SCHEMA_SQL


def run(directory, port):
    directory = directory.resolve()
    if not directory.is_relative_to(Path('/workspace')) or not 1024 <= port <= 63535:
        raise ValueError('Use an isolated /workspace directory and an unprivileged local port')
    directory.mkdir(parents=True, exist_ok=False)
    owner='synthetic_jev_trial_owner'
    frozen=json.dumps({'id':owner,'billing':{'plan':'free','status':'active'}},separators=(',',':'))
    guard="INSERT INTO d1_command_guard(ok) VALUES(CASE WHEN EXISTS(SELECT 1 FROM app_state u WHERE u.name=? AND u.payload=?) THEN 1 ELSE 0 END)"
    params=[owner,owner,owner,'2026-10',0,1,0,0,3,300,10,1000,0,0,0,0,'2026-10',1,1]
    source='''const schema=SCHEMA, quota=QUOTA, guard=GUARD, frozen=FROZEN, base=PARAMS;
export default {async fetch(request,env) {
  if(request.method!=="POST") return new Response("method",{status:405});
  const {case:kind}=await request.json();
  if(kind==="initialize") {
    const r=await env.DB.batch([...schema.map(sql=>env.DB.prepare(sql)),env.DB.prepare("INSERT INTO app_state(name,payload,updated_at) VALUES(?,?,?)").bind("user:"+base[0],frozen,1)]);
    return Response.json({success:true,meta:r.map(x=>x.meta)});
  }
  if(!["trial","roll-month","stale-guard"].includes(kind)) return new Response("case",{status:422});
  const p=[...base];
  if(kind==="roll-month") {p[3]=p[16]="2026-11";p[5]=p[17]=2;p[18]=0;}
  let admitted=true,meta=[];
  try {
    const r=await env.DB.batch([env.DB.prepare(guard).bind("user:"+base[0],kind==="stale-guard"?"{}":frozen),env.DB.prepare("DELETE FROM d1_command_guard"),env.DB.prepare(quota).bind(...p)]);
    meta=r.map(x=>x.meta);
  } catch {admitted=false;}
  const usage=await env.DB.prepare("SELECT jev_trial_calls,jev_reserved_microusd,month,writes FROM ledger_plan_usage WHERE owner_id=?").bind(base[0]).all();
  const clean=await env.DB.prepare("SELECT COUNT(*) AS guards FROM d1_command_guard").all();
  return Response.json({admitted,usage:usage.results[0],guards:clean.results[0].guards,meta,readMeta:[usage.meta,clean.meta]});
}};
'''
    for key,value in {'SCHEMA':SCHEMA_SQL,'QUOTA':_USAGE_SQL,'GUARD':guard,'FROZEN':frozen,'PARAMS':params}.items(): source=source.replace(key,json.dumps(value))
    (directory/'worker.mjs').write_text(source)
    (directory/'wrangler.jsonc').write_text(json.dumps({'name':'norulo-jev-trial-native-local','main':'worker.mjs','compatibility_date':'2026-09-23','d1_databases':[{'binding':'DB','database_name':'synthetic-jev-trial-local','database_id':'00000000-0000-4000-8000-000000000015'}]}))
    env={**os.environ,'XDG_CONFIG_HOME':'/workspace/.cache/config','XDG_CACHE_HOME':'/workspace/.cache','WRANGLER_LOG_PATH':str(directory/'wrangler.log'),'WRANGLER_SEND_METRICS':'false','GOMAXPROCS':'2'}
    command=['node',str(ROOT/'cloudflare/server/node_modules/wrangler/wrangler-dist/cli.js'),'dev','--local','--ip','127.0.0.1','--port',str(port),'--config',str(directory/'wrangler.jsonc'),'--persist-to',str(directory/'state')]
    results=[]
    def request(case):
        raw=json.dumps({'case':case}).encode()
        req=urllib.request.Request(f'http://127.0.0.1:{port}',data=raw,headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=10) as r: data=json.load(r)
        results.append({'case':case,**data});return data
    with (directory/'dev.log').open('w') as log:
        process=subprocess.Popen(command,cwd=directory,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try:
            for _ in range(180):
                if process.poll() is not None: raise RuntimeError('local workerd exited; inspect dev.log')
                # GET health only; never retry initialization/admission writes.
                try:
                    urllib.request.urlopen(f'http://127.0.0.1:{port}',timeout=0.5)
                except urllib.error.HTTPError as e:
                    if e.code==405:break
                except (urllib.error.URLError,TimeoutError):pass
                time.sleep(0.25)
            else:raise RuntimeError('local workerd startup deadline exceeded')
            request('initialize')
            # Test the last admission and constraint race boundary without a stress loop.
            for _ in range(19): assert request('trial')['admitted']
            stale=request('stale-guard');assert not stale['admitted'] and stale['usage']['jev_trial_calls']==19 and stale['guards']==0
            final=request('trial');assert final['admitted'] and final['usage']['jev_trial_calls']==20
            denied=request('trial');assert not denied['admitted'] and denied['usage']['jev_trial_calls']==20 and denied['guards']==0
            month=request('roll-month');assert month['admitted'] and month['usage']['jev_trial_calls']==20 and month['usage']['month']=='2026-11'
            # Return to the current month only in this isolated fixture; production clock fences remain unchanged.
            # Paid boundary is already covered with concurrent canonical adapters in Python regressions.
            report={'schemaVersion':15,'scope':'isolated workerd and local D1; synthetic Owner; no providers or production requests','httpRequests':len(results),'trialCallsAdmitted':20,'staleGuardCharged':False,'twentyFirstDenied':True,'monthResetRenewsTrials':False,'results':results}
            (directory/'result.json').write_text(json.dumps(report,indent=2)+'\n')
            print(json.dumps({k:v for k,v in report.items() if k!='results'}))
        finally:
            try: os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError: pass
            try:process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL);process.wait(timeout=5)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--port',type=int,default=8788)
    args=parser.parse_args();run(args.output,args.port)

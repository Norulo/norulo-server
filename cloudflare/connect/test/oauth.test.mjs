import {test} from 'node:test';
import assert from 'node:assert/strict';
import worker,{Authorization} from '../src/index.js';
import {authorizationSelection,handleMcp,RESOURCE,AUTHORIZE,SCOPES} from '../src/core.js';

class MemoryKV {
  values=new Map();
  async get(k,o){const v=this.values.get(k);return v===undefined?null:(o==='json'||o?.type==='json')?JSON.parse(v):v;}
  async put(k,v){this.values.set(k,v);}
  async delete(k){this.values.delete(k);}
  async list(o={}){return {keys:[...this.values.keys()].filter(k=>k.startsWith(o.prefix||'')).map(name=>({name})),list_complete:true,cursor:''};}
}
const cookie='nr_session=test-session',key='nrk_test_backend_delegated_credential';
function setup(){
  const calls=[],env={OAUTH_KV:new MemoryKV(),NORULO_SERVER:{fetch:async req=>{
    calls.push({url:req.url,method:req.method,authorization:req.headers.get('Authorization')});
    const p=new URL(req.url).pathname;
    if(req.headers.get('Cookie')!==cookie&&req.headers.get('Authorization')!=='Bearer '+key)return Response.json({error:{code:'UNAUTHENTICATED'}},{status:401});
    if(p==='/api/v1/me')return Response.json({id:'user_test',workspace:{id:'workspace_test',name:'Demo ledger',role:'owner'},scopes:SCOPES});
    if(p==='/api/v1/workspaces')return Response.json({items:[{id:'workspace_test',name:'Demo ledger'}]});
    if(p==='/api/v1/projects')return Response.json({items:[{id:'project_demo',name:'Review <script>bad</script>'}],nextCursor:null});
    if(p==='/api-keys'&&req.method==='POST'){const body=await req.json();assert.deepEqual(body.restrictions.projectIds,['project_demo']);assert.equal(body.restrictions.shared,false);assert.equal(body.restrictions.workspaceId,'workspace_test');return Response.json({id:'key_test',key},{status:201});}
    return Response.json({items:[]});
  }}};
  const ctx={waitUntil:()=>{}};return {env,calls,ctx};
}
async function register(env,ctx){const r=await worker.fetch(new Request('https://mcp.norulo.com/oauth/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({client_name:'Test client',redirect_uris:['https://client.example/callback'],token_endpoint_auth_method:'none',grant_types:['authorization_code','refresh_token'],response_types:['code']})}),env,ctx);assert.equal(r.status,201,await r.clone().text());return r.json();}
async function begin(env,ctx){
  const client=await register(env,ctx),verifier='a'.repeat(64);
  const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(verifier));const challenge=Buffer.from(digest).toString('base64url');
  const u=new URL(AUTHORIZE);u.search=new URLSearchParams({client_id:client.client_id,redirect_uri:'https://client.example/callback',response_type:'code',scope:'profile:read projects:read expenses:read',resource:RESOURCE,state:'state-bound',code_challenge:challenge,code_challenge_method:'S256'});
  const handler=new Authorization(ctx,env),r=await handler.fetch(new Request(u,{headers:{Cookie:cookie}}));
  assert.equal(r.status,200,await r.clone().text());assert.match(r.headers.get('Content-Security-Policy'),/form-action 'self' https:\/\/client\.example;/);assert(!r.headers.get('Content-Security-Policy').includes('*'));assert.equal(r.headers.get('Referrer-Policy'),'same-origin','native consent POST must preserve same-origin Origin without cross-origin referrers');const html=await r.text();assert(!html.includes('<script>bad</script>'));assert(html.includes('Review &#60;script&#62;'));
  const handle=html.match(/name="handle" value="([^"]+)"/)[1];
  const consentCookies=r.headers.getSetCookie().map(c=>c.split(';')[0]).join('; ');
  return {handler,u,client,verifier,handle,cookies:cookie+'; '+consentCookies};
}
async function approve(env,ctx){
  const b=await begin(env,ctx),form=new URLSearchParams({handle:b.handle,decision:'approve',project:'project_demo'});for(const s of ['profile:read','projects:read','expenses:read'])form.append('scope',s);
  // The mock accepts the canonical session cookie plus consent cookie.
  const f=env.NORULO_SERVER.fetch;env.NORULO_SERVER.fetch=req=>{const h=new Headers(req.headers);if(h.get('Cookie')?.startsWith(cookie))h.set('Cookie',cookie);return f(new Request(req,{headers:h}));};
  const r=await b.handler.fetch(new Request(b.u,{method:'POST',headers:{Cookie:b.cookies,Origin:'https://norulo.com','Content-Type':'application/x-www-form-urlencoded'},body:form}));
  assert.equal(r.status,303,await r.clone().text());const back=new URL(r.headers.get('Location'));assert.equal(back.searchParams.get('state'),'state-bound');return {...b,code:back.searchParams.get('code')};
}
async function token(env,ctx,body){return worker.fetch(new Request('https://mcp.norulo.com/oauth/token',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams(body)}),env,ctx);}

test('OAuth discovery and unauthenticated MCP challenge',async()=>{const {env,ctx}=setup();let r=await worker.fetch(new Request('https://mcp.norulo.com/.well-known/oauth-authorization-server'),env,ctx);assert.equal(r.status,200);const m=await r.json();assert.equal(m.authorization_endpoint,AUTHORIZE);assert.equal(m.issuer,'https://mcp.norulo.com');r=await worker.fetch(new Request(RESOURCE,{method:'POST',body:'{}'}),env,ctx);assert.equal(r.status,401);assert.match(r.headers.get('WWW-Authenticate'),/resource_metadata/);});
test('PKCE code flow, encrypted delegated credential, token refresh, scoped MCP and revocation',async()=>{
  const {env,ctx,calls}=setup(),b=await approve(env,ctx);
  assert(![...env.OAUTH_KV.values.values()].some(v=>v.includes(key)),'backend credential must be encrypted at rest');
  let r=await token(env,ctx,{grant_type:'authorization_code',client_id:b.client.client_id,code:b.code,redirect_uri:'https://client.example/callback',code_verifier:b.verifier,resource:RESOURCE});assert.equal(r.status,200,await r.clone().text());let t=await r.json();assert(t.access_token&&t.refresh_token);
  r=await worker.fetch(new Request(RESOURCE,{method:'POST',headers:{Authorization:'Bearer '+t.access_token},body:JSON.stringify({jsonrpc:'2.0',id:1,method:'tools/list'})}),env,ctx);assert.equal(r.status,200);let list=(await r.json()).result.tools;assert(list.some(t=>t.name==='listExpenses'));assert(!list.some(t=>t.name==='createExpense'));
  r=await worker.fetch(new Request(RESOURCE,{method:'POST',headers:{Authorization:'Bearer '+t.access_token},body:JSON.stringify({id:2,method:'tools/call',params:{name:'connection_status',arguments:{}}})}),env,ctx);assert.equal(JSON.parse((await r.json()).result.content[0].text).connected,true);
  r=await token(env,ctx,{grant_type:'refresh_token',client_id:b.client.client_id,refresh_token:t.refresh_token,resource:RESOURCE});assert.equal(r.status,200,await r.clone().text());t=await r.json();
  r=await token(env,ctx,{grant_type:'refresh_token',client_id:b.client.client_id,refresh_token:t.refresh_token,resource:'https://other.example/mcp'});assert.equal(r.status,400,'token cannot be retargeted');
  assert(calls.some(c=>c.url.endsWith('/api-keys')&&c.method==='POST'));
  // RFC7009 revokes the grant when its refresh token is presented.
  r=await token(env,ctx,{client_id:b.client.client_id,token:t.refresh_token});assert.equal(r.status,200,await r.clone().text());
  r=await worker.fetch(new Request(RESOURCE,{method:'POST',headers:{Authorization:'Bearer '+t.access_token},body:'{}'}),env,ctx);assert.equal(r.status,401);
});
test('Wrong PKCE verifier cannot exchange a code',async()=>{const {env,ctx}=setup(),b=await approve(env,ctx);const r=await token(env,ctx,{grant_type:'authorization_code',client_id:b.client.client_id,code:b.code,redirect_uri:'https://client.example/callback',code_verifier:'b'.repeat(64)});assert.equal(r.status,400);});
test('Foreign, null and missing origins cannot create a delegated key',async()=>{
  for(const origin of ['https://evil.example','null',undefined]){
    const {env,ctx,calls}=setup(),h=new Authorization(ctx,env),headers={Cookie:cookie};
    if(origin!==undefined)headers.Origin=origin;
    const r=await h.fetch(new Request(AUTHORIZE,{method:'POST',headers,body:'decision=approve'}));
    assert.equal(r.status,403);assert(!calls.some(c=>c.method==='POST'));
  }
});
test('Cannot grant unknown projects or viewer writes',()=>{const me={workspace:{id:'w',role:'viewer'}};assert.throws(()=>authorizationSelection(new URLSearchParams('scope=profile:read&scope=expenses:write&project=p'),me,[{id:'p'}]),/ROLE_FORBIDDEN/);assert.throws(()=>authorizationSelection(new URLSearchParams('scope=profile:read&project=other'),me,[{id:'p'}]),/INVALID_TARGET/);});
test('MCP cannot dispatch an ungranted mutation',async()=>{const {env,calls}=setup();const r=await handleMcp(new Request(RESOURCE,{method:'POST',body:JSON.stringify({id:1,method:'tools/call',params:{name:'createExpense',arguments:{body:{}}}})}),env,{auth:{scope:['profile:read','expenses:read']},props:{apiKey:key}});assert.equal((await r.json()).result.isError,true);assert.equal(calls.length,0);});
test('Authorization code replay is refused',async()=>{const {env,ctx}=setup(),b=await approve(env,ctx);const body={grant_type:'authorization_code',client_id:b.client.client_id,code:b.code,redirect_uri:'https://client.example/callback',code_verifier:b.verifier};assert.equal((await token(env,ctx,body)).status,200);assert.equal((await token(env,ctx,body)).status,400);});


test('A second consent submission reports used or expired without issuing another credential',async()=>{
  const {env,ctx,calls}=setup(),b=await approve(env,ctx);
  const before=calls.filter(c=>c.method==='POST').length;
  const r=await b.handler.fetch(new Request(b.u,{method:'POST',headers:{Cookie:b.cookies,Origin:'https://norulo.com'},body:new URLSearchParams({handle:b.handle,decision:'approve'})}));
  assert.equal(r.status,400);assert.match(await r.text(),/已提交或已过期/);
  assert.equal(calls.filter(c=>c.method==='POST').length,before);
});
test('Consent remains bound to its original actor and ledger',async()=>{
  for(const saved of [{userId:'other_user',workspaceId:'workspace_test'},{userId:'user_test',workspaceId:'other_workspace'}]){
    const {env,ctx,calls}=setup(),b=await begin(env,ctx);
    await env.OAUTH_KV.put('norulo-consent:'+b.handle,JSON.stringify(saved));
    const r=await b.handler.fetch(new Request(b.u,{method:'POST',headers:{Cookie:cookie,Origin:'https://norulo.com'},body:new URLSearchParams({handle:b.handle,decision:'approve'})}));
    assert.equal(r.status,403);assert(!calls.some(c=>c.method==='POST'));
  }
});

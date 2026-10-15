import {WorkerEntrypoint} from 'cloudflare:workers';
import {OAuthAuthorizationServer,OAuthResourceServer,AuthorizationError,CimdFetchError} from '@cloudflare/workers-oauth-provider';
import {ISSUER,RESOURCE,AUTHORIZE,SCOPES,handleAuthorization,handleMcp,json,html,escape} from './core.js';

const authorizationServer=new OAuthAuthorizationServer({
  issuer:ISSUER,resources:[RESOURCE],authorizeEndpoint:AUTHORIZE,
  tokenEndpoint:ISSUER+'/oauth/token',clientRegistrationEndpoint:ISSUER+'/oauth/register',
  scopesSupported:[...SCOPES,'offline_access'],accessTokenTTL:3600,refreshTokenTTL:2592000,
  clientRegistrationTTL:7776000,clientIdMetadataDocumentEnabled:true,
  onError:({error})=>{console.error(JSON.stringify({code:'OAUTH_PROTOCOL_ERROR',error:typeof error==='string'?error:'protocol'}));},
});
const resourceServer=new OAuthResourceServer({
  resourceMetadata:{resource:RESOURCE,authorization_servers:[ISSUER],resource_name:'Norulo'},
  requiredScopes:['profile:read','projects:read','categories:read','expenses:read','reports:read'],
  validateToken:env=>(resource,token)=>authorizationServer.validateToken(resource,token,env),
  handler:{fetch:handleMcp},
});

// Only norulo-web's private service binding reaches this entrypoint with the host-only Norulo session.
export class Authorization extends WorkerEntrypoint {
  async fetch(request){
    try{return await handleAuthorization(request,this.env,authorizationServer.getOAuthApi(this.env));}
    catch(error){
      if(error instanceof AuthorizationError&&error.redirectTo&&request.method==='GET')return new Response(null,{status:303,headers:{Location:error.redirectTo,'Cache-Control':'no-store','Referrer-Policy':'no-referrer'}});
      if(error instanceof AuthorizationError||error instanceof CimdFetchError)return html('<h1>无法完成授权</h1><p>'+escape(error instanceof AuthorizationError?error.description:'无法验证此客户端。')+'</p><p>请返回 ChatGPT 或 Codex，重新发起连接。</p>');
      console.error(JSON.stringify({code:'NORULO_AUTHORIZATION_FAILED'}));
      return json({error:'Authorization unavailable. Restart the connection from your client.'},503);
    }
  }
}
export default {
  async fetch(request,env,ctx){
    const u=new URL(request.url);
    if(u.hostname!=='mcp.norulo.com')return json({error:'Not found'},404);
    try{
      if(u.pathname==='/mcp'||u.pathname.startsWith('/mcp/')||u.pathname.startsWith('/.well-known/oauth-protected-resource'))return await resourceServer.fetch(request,env,ctx);
      if(u.pathname==='/health')return json({ok:true,service:'Norulo OAuth MCP',version:'2.0.0'});
      if(u.pathname==='/')return html('<h1>Norulo for ChatGPT &amp; Codex</h1><p>在插件中点击连接，登录 Norulo 后选择允许访问的账本、项目和权限。</p><section><h2>添加 MCP 连接</h2><p><code>https://mcp.norulo.com/mcp</code></p><p>认证方式：OAuth。无需复制 API Key。</p></section><p><a href="https://norulo.com/api-keys">在 Norulo 管理已授权连接</a>：撤销对应 OAuth 密钥可停止其访问。</p>');
      return await authorizationServer.fetch(request,env,ctx);
    }catch{console.error(JSON.stringify({code:'NORULO_OAUTH_REQUEST_FAILED'}));return json({error:'Service unavailable'},503);}
  },
};

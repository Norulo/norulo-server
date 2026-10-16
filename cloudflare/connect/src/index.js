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
      if(error instanceof AuthorizationError||error instanceof CimdFetchError)return html('<h1>Unable to authorize</h1><p>'+escape(error instanceof AuthorizationError?error.description:'This client could not be verified.')+'</p><p>Return to your AI app (such as Claude, ChatGPT or Codex) and start a new connection.</p>');
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
      if(u.pathname==='/')return html('<h1>Norulo for AI agents</h1><p>Add Norulo as a custom connector in Claude, ChatGPT or Codex, click Connect, sign in to Norulo, and choose the ledger, projects and permissions to allow.</p><section><h2>Add an MCP connection</h2><p><code>https://mcp.norulo.com/mcp</code></p><p>Authentication: OAuth. No API key to copy.</p></section><p><a href="https://norulo.com/api-keys">Manage authorized connections in Norulo</a>. Revoke the corresponding OAuth key to stop its access.</p>');
      return await authorizationServer.fetch(request,env,ctx);
    }catch{console.error(JSON.stringify({code:'NORULO_OAUTH_REQUEST_FAILED'}));return json({error:'Service unavailable'},503);}
  },
};

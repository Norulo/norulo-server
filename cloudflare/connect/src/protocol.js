export const SUPPORTED_PROTOCOL_VERSIONS=['2026-07-28','2025-11-25','2025-06-18','2024-11-05'];
const CURRENT_PROTOCOL_VERSION=SUPPORTED_PROTOCOL_VERSIONS[0];
export const SERVER_CAPABILITIES={tools:{listChanged:false}};
export const SERVER_INFO={name:'Norulo',version:'2.0.0'};

export function negotiatedProtocolVersion(requested){
  return SUPPORTED_PROTOCOL_VERSIONS.includes(requested)?requested:CURRENT_PROTOCOL_VERSION;
}

export function protocolContext(request,message){
  const metaVersion=message.params?._meta?.['io.modelcontextprotocol/protocolVersion'];
  const headerVersion=request.headers.get('MCP-Protocol-Version');
  const declared=metaVersion??headerVersion;
  if(declared!=null&&!SUPPORTED_PROTOCOL_VERSIONS.includes(declared))return {error:{code:-32022,message:'Unsupported protocol version',data:{supported:SUPPORTED_PROTOCOL_VERSIONS,requested:declared}}};
  if(metaVersion&&headerVersion&&metaVersion!==headerVersion)return {error:{code:-32600,message:'Protocol version metadata and header must match'}};
  // Keep unversioned existing Sites clients on their original response shape.
  return {version:declared??(message.method==='initialize'?negotiatedProtocolVersion(message.params?.protocolVersion):'2024-11-05')};
}

export function discoveryResult(instructions){
  return {resultType:'complete',supportedVersions:SUPPORTED_PROTOCOL_VERSIONS,capabilities:SERVER_CAPABILITIES,_meta:{'io.modelcontextprotocol/serverInfo':SERVER_INFO},instructions,ttlMs:0,cacheScope:'public'};
}

export function protocolReply(message,context,body){
  let result=body.result;
  if(result&&context.version===CURRENT_PROTOCOL_VERSION&&message.method!=='initialize'){
    result={resultType:'complete',...result};
    if(['server/discover','tools/list'].includes(message.method))result={ttlMs:0,cacheScope:'public',...result};
  }
  return {jsonrpc:'2.0',id:message.id??null,...body,...(result?{result}:{})};
}

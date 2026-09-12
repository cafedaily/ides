/* User-configured model requests go directly from this device to that provider. */
const API={on:true,why:"",async probe(){return true;},async bridges(limit=24){return {bridges:localGraph().bridges.slice(0,limit)};},async path(a,b){return localPath(a,b);}};
function payloadState(st){return clone({ideas:st.ideas||[],sparks:st.sparks||[],cold:st.cold||[],conf:st.conf||defaultConf()});}
function selectedModel(action){
  const models=S.conf.models||[],id=(S.conf.route||{})[action]||S.conf.defaultModel;
  return models.find(model=>model.id===id)||(!id?models[0]:null);
}
function validateModel(model){
  if(!model || !model.name?.trim())throw new Error("请填写模型配置名称。");
  let url;try{url=new URL(model.base);}catch(e){throw new Error("请输入完整的服务地址，例如 https://api.example.com/v1。");}
  if(!["https:","http:"].includes(url.protocol)||url.username||url.password||url.search||url.hash)throw new Error("服务地址必须为 HTTP/HTTPS，且不含账号、查询参数或片段。");
  if(!model.model?.trim())throw new Error("请填写服务商提供的模型 ID。");
  if(location.protocol==="https:" && url.protocol==="http:" && !["localhost","127.0.0.1","[::1]"].includes(url.hostname))throw new Error("HTTPS 页面需要 HTTPS 模型地址。使用本地模型时可填写 localhost 地址。");
  return url.href.replace(/\/chat\/completions\/?$/,"").replace(/\/$/,"");
}
const MODEL_REQUESTS=new Set();
async function requestModel(model,body,opts={}){
  const base=validateModel(model),controller=new AbortController();MODEL_REQUESTS.add(controller);
  const abort=()=>controller.abort();opts.signal?.addEventListener("abort",abort,{once:true});
  if(opts.signal?.aborted)controller.abort();
  const timer=setTimeout(()=>controller.abort(new Error("请求超时，请检查服务后重试。")),opts.timeout||60000);
  try{
    const response=await fetch(base+"/chat/completions",{method:"POST",credentials:"omit",referrerPolicy:"no-referrer",redirect:"error",signal:controller.signal,
      headers:{"Content-Type":"application/json",...(model.key?{Authorization:"Bearer "+model.key}:{})},body:JSON.stringify({...body,model:model.model})});
    if(!response.ok)throw new Error(response.status===401||response.status===403?"模型鉴权失败，请检查 API Key 和访问权限。":response.status===429?"模型请求过于频繁或额度不足，请稍后重试。":"模型服务返回 HTTP "+response.status+"，请检查地址和模型 ID。");
    if(!body.stream){
      const value=await response.json();const text=value.choices?.[0]?.message?.content;
      if(typeof text!=="string")throw new Error("模型响应没有文本内容，请确认使用 OpenAI 兼容接口。");
      return {ok:true,text};
    }
    if(!response.body)throw new Error("浏览器无法读取流式响应。");
    const reader=response.body.getReader(),decoder=new TextDecoder();let buffer="",text="",finished=false;
    function frame(value){
      const raw=value.split(/\r?\n/).filter(line=>line.startsWith("data:")).map(line=>line.slice(5).trimStart()).join("\n");
      if(!raw)return;
      if(raw==="[DONE]"){finished=true;return;}
      let event;try{event=JSON.parse(raw);}catch(e){throw new Error("模型流式响应格式错误。");}
      if(event.error)throw new Error("模型流式请求失败，请检查服务配置。");
      const part=event.choices?.[0];const delta=part?.delta?.content;
      if(typeof delta==="string"){text+=delta;opts.onText?.({text,delta});}
      if(part?.finish_reason)finished=true;
    }
    try{
      while(!finished){const chunk=await reader.read();if(chunk.done){buffer+=decoder.decode();if(buffer.trim())frame(buffer);break;}
        buffer+=decoder.decode(chunk.value,{stream:true});let match;
        while((match=/\r?\n\r?\n/.exec(buffer))){const item=buffer.slice(0,match.index);buffer=buffer.slice(match.index+match[0].length);frame(item);if(finished)break;}}
      if(!finished)throw new Error("连接提前断开，回答未完成，请重试。");
      return {ok:true,text};
    }finally{await reader.cancel().catch(()=>{});reader.releaseLock();}
  }catch(error){
    if(controller.signal.aborted)throw new Error(opts.signal?.aborted?"已取消模型请求。":"请求超时或已取消，请重试。");
    if(error instanceof TypeError)throw new Error("无法连接模型。请检查网络与地址，并确认服务允许浏览器跨域访问（CORS）。");
    throw error;
  }finally{clearTimeout(timer);opts.signal?.removeEventListener("abort",abort);MODEL_REQUESTS.delete(controller);}
}
async function testModel(model,signal){return requestModel(model,{messages:[{role:"user",content:"Reply with OK."}],max_tokens:16},{signal,timeout:15000});}

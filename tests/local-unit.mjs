import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';
const source=path.resolve(import.meta.dirname,'../web/src');
const ctx=vm.createContext({TextDecoder,TextEncoder,AbortController,URL,setTimeout,clearTimeout,location:{protocol:'https:'},clone:structuredClone,
  S:{ideas:[],sparks:[],cold:[],conf:{models:[],route:{}}}});
vm.runInContext(fs.readFileSync(path.join(source,'03_api.js'),'utf8')+'\n'+fs.readFileSync(path.join(source,'local_graph.js'),'utf8')+';globalThis.exposed={requestModel,validateModel,localGraph,localPath,localAliases};',ctx);
const {requestModel,validateModel,localGraph,localPath,localAliases}=ctx.exposed;
const model={id:'m',name:'User model',base:'https://example.test/v1',model:'self-chosen',key:'SYNTHETIC_KEY'};
assert.throws(()=>validateModel({...model,base:'https://user:password@example.test'}));
let lastRequest;
ctx.fetch=async(url,opts)=>{lastRequest={url,opts};let sent=false;return {ok:true,body:{getReader:()=>({read:async()=>sent?{done:true}:(sent=true,{done:false,value:new TextEncoder().encode('data: {"choices":[{"delta":{"content":"部分"}}]}\n\n')}),cancel:async()=>{},releaseLock(){}})}};};
await assert.rejects(requestModel(model,{stream:true}),/连接提前断开/);
assert.equal(lastRequest.url,'https://example.test/v1/chat/completions');assert.equal(lastRequest.opts.credentials,'omit');assert.equal(lastRequest.opts.headers.Authorization,'Bearer SYNTHETIC_KEY');
assert.equal(JSON.parse(lastRequest.opts.body).model,'self-chosen');
ctx.fetch=async()=>({ok:false,status:401});await assert.rejects(requestModel(model,{}),/鉴权失败/);
ctx.fetch=async()=>{throw new TypeError('network failure');};
// The mock error originates outside the VM realm, so only browser integration asserts the CORS wording.
await assert.rejects(requestModel(model,{}));
assert.throws(()=>localAliases({aliases:{'循环甲':'循环乙','循环乙':'循环甲'}}),/循环/);
ctx.S.ideas=[{id:'a',title:'LLM 推理',seed:'研究 LLM 推理的每一步。',grew:[]},{id:'b',title:'大模型推理',seed:'大模型推理的每步需要解释。',grew:[]}];
const graph=localGraph();assert.ok(graph.bridges.length);assert.equal(localGraph(),graph);assert.ok(localPath('a','b').found);
assert.ok(graph.bridges.some(bridge=>bridge.a_say.text.includes('LLM')||bridge.b_say.text.includes('LLM')));
ctx.S.ideas.pop();assert.equal(localGraph().documents.length,1);assert.equal(localPath('a','b').found,false);
console.log('Model routing, direct transport, error handling, lexical aliases, cache invalidation and original evidence passed');

/* 后端。有就用，没有就当它不存在——整个应用在纯本地下必须一样能跑。

   探测只做一次，失败就永久关掉，不重试、不轮询。一个连不上的后端不该
   让每个页面都卡半秒。 */
const API = {
  on: false, tried: false, base: "", why: "",
  health: null,

  async probe(force=false){
    if(this.pending) return this.pending;
    if(this.tried && !force) return this.on;
    this.pending=(async()=>{
      this.tried=true;
      try{
        const h=await this._get("/api/health");
        if(!h || h.fmt!=="yang.jsonl") throw new Error("这不是养想法的服务");
        this.health=h; this.available=true;
        const session=await this._get("/api/session");
        this.on=!!session.authenticated; this.why="";
      }catch(e){ this.on=false; this.why=e.status===401 ? "请登录自己的空间" : e.message; }
      return this.on;
    })();
    try{ return await this.pending; }finally{ this.pending=null; }
  },

  async _get(p){
    const r = await fetch(p, { cache:"no-store" });
    const j = await r.json().catch(()=>null);
    if(!r.ok) throw Object.assign(new Error((j && j.error) || ("HTTP " + r.status)), {status:r.status, details:j});
    return j;
  },
  async _post(p, body, opts){
    opts = opts || {};
    const r = await fetch(p, { method:"POST", cache:"no-store",
      signal:opts.signal,
      headers:{ "Content-Type":"application/json" },
      body: JSON.stringify(body === undefined ? null : body) });
    const j = await r.json().catch(()=>null);
    if(!r.ok) throw Object.assign(new Error((j && j.error) || ("HTTP " + r.status)), {status:r.status, details:j});
    return j;
  },
  async _postStream(p, body, opts){
    opts = opts || {};
    const r = await fetch(p, { method:"POST", cache:"no-store",
      signal:opts.signal,
      headers:{ "Content-Type":"application/json" },
      body: JSON.stringify(body === undefined ? null : body) });
    if(!r.ok){
      const j = await r.json().catch(()=>null);
      throw Object.assign(new Error((j && j.error) || ("HTTP " + r.status)), {status:r.status, details:j});
    }
    if(!r.body || !r.body.getReader) throw new Error("这个浏览器不支持流式读取。");
    const reader = r.body.getReader();
    const dec = new TextDecoder("utf-8");
    let buf = "", text = "";
    function take(frame){
      const lines = frame.replace(/\r/g, "").split("\n");
      const data = [];
      lines.forEach(line=>{
        if(line.indexOf("data:")===0) data.push(line.slice(5).replace(/^ /,""));
      });
      if(!data.length) return;
      let ev;
      try{ ev = JSON.parse(data.join("\n")); }
      catch(e){ throw new Error("模型返回了无法解析的流。"); }
      if(!ev || typeof ev !== "object") return;
      if(ev.type === "delta"){
        text += String(ev.text || "");
        if(opts.onText) opts.onText({ text:text, delta:String(ev.text || "") });
      }else if(ev.type === "error"){
        throw new Error(ev.error || "模型调用失败");
      }else if(ev.type === "done"){
        return "done";
      }
    }
    while(true){
      const part = await reader.read();
      if(part.done) break;
      buf += dec.decode(part.value, { stream:true });
      let at;
      while((at = buf.search(/\r?\n\r?\n/)) >= 0){
        const frame = buf.slice(0, at);
        const m = buf.match(/\r?\n\r?\n/);
        buf = buf.slice(at + m[0].length);
        if(take(frame) === "done"){
          try{ await reader.cancel(); }catch(e){}
          return { ok:true, text:text };
        }
      }
    }
    buf += dec.decode();
    if(buf.trim() && take(buf)==="done") return {ok:true,text};
    throw new Error("连接提前断开，回答尚未完成，请重试。");
  },

  pull(){ return this._get("/api/state"); },
  push(st, mode){ return this._post("/api/state?mode=" + (mode||"merge"),
    { ideas:st.ideas, sparks:st.sparks, cold:st.cold, conf:st.conf }); },
  graph(){ return this._get("/api/graph"); },
  bridges(n){ return this._get("/api/bridges?limit=" + (n||20)); },
  related(id){ return this._get("/api/related?id=" + encodeURIComponent(id)); },
  path(a,b){ return this._get("/api/path?a=" + encodeURIComponent(a) + "&b=" + encodeURIComponent(b)); },
  search(q){ return this._get("/api/search?q=" + encodeURIComponent(q)); },
};

/* Revision sync uses a captured snapshot; edits during a request remain queued. */
const SYNC = {base:null, running:null, dirty:false, conflict:null, error:""};
let pushT=null;
function canonical(value){
  if(Array.isArray(value)) return "["+value.map(canonical).join(",")+"]";
  if(value && typeof value==="object") return "{"+Object.keys(value).sort().map(k=>JSON.stringify(k)+":"+canonical(value[k])).join(",")+"}";
  return JSON.stringify(value);
}
function payloadState(st){ return JSON.parse(JSON.stringify({ideas:st.ideas||[],sparks:st.sparks||[],cold:st.cold||[],conf:st.conf||defaultConf()})); }
function syncDelta(base, local){
  const change={base_revision:base.revision, changes:{}};
  for(const name of ["ideas","sparks","cold"]){
    const old=new Map((base[name]||[]).map(x=>[x.id,x])), current=new Map((local[name]||[]).map(x=>[x.id,x]));
    const upsert=[...current.values()].filter(x=>canonical(x)!==canonical(old.get(x.id)));
    const deleted=[...old.keys()].filter(id=>!current.has(id));
    if(upsert.length || deleted.length) change.changes[name]={upsert,delete:deleted};
  }
  if(canonical(base.conf)!==canonical(local.conf)) change.conf=local.conf;
  return change;
}
function mergeThree(base, local, remote, choose){
  const result=payloadState(local), conflicts=[];
  function select(key,b,l,r){
    if(canonical(l)===canonical(b)) return r;
    if(canonical(r)===canonical(b) || canonical(r)===canonical(l)) return l;
    conflicts.push(key); return choose==="remote" ? r : l;
  }
  for(const name of ["ideas","sparks","cold"]){
    const maps=[base,local,remote].map(st=>new Map((st[name]||[]).map(x=>[x.id,x])));
    const ids=new Set(maps.flatMap(m=>[...m.keys()]));
    result[name]=[...ids].map(id=>select(name+":"+id,...maps.map(m=>m.get(id)))).filter(Boolean);
  }
  result.conf=select("模型与图谱设置",base.conf,local.conf,remote.conf);
  return {state:result,conflicts};
}
function syncUp(){
  if(SPACE!=="private") return;
  SYNC.dirty=true; clearTimeout(pushT);
  pushT=setTimeout(()=>flushSync(),600);
  paintSession();
}
async function flushSync(){
  clearTimeout(pushT);
  if(SYNC.running) return SYNC.running;
  if(!API.on || SPACE!=="private" || !SYNC.base || SYNC.conflict) return;
  SYNC.running=(async()=>{
    while(SYNC.dirty && API.on && SPACE==="private" && !SYNC.conflict){
      SYNC.dirty=false;
      const sent=payloadState(S), change=syncDelta(SYNC.base,sent);
      if(!Object.keys(change.changes).length && !("conf" in change)) continue;
      try{
        const ack=await API._post("/api/sync",change);
        // Only clear a transient key if it is still the one acknowledged by the server.
        for(const m of S.conf.models||[]){
          const delivered=(sent.conf.models||[]).find(x=>x.id===m.id);
          if(delivered && m.key===delivered.key && delivered.key){ m.keyConfigured=true; delete m.key; }
          if(delivered && delivered.clear_key && m.clear_key){ m.keyConfigured=false; delete m.clear_key; }
        }
        SYNC.base={...safeState(sent),revision:ack.revision};
        for(const m of SYNC.base.conf.models||[]) if((sent.conf.models||[]).find(x=>x.id===m.id)?.clear_key) m.keyConfigured=false;
        SYNC.error=""; S.syncBase=SYNC.base;
        // Persist acknowledged baseline with latest edits, without scheduling a new write.
        try{ localStorage.setItem(LS,JSON.stringify(safeState(S))); }catch(e){}
        await dbWrite(); GV.bridges=null;
      }catch(e){
        SYNC.dirty=true;
        if(e.status===409){
          try{
            const remote=await API.pull(), merged=mergeThree(SYNC.base,payloadState(S),remote);
            if(merged.conflicts.length){ SYNC.conflict={remote,conflicts:merged.conflicts}; }
            else{ Object.assign(S,merged.state); SYNC.base=remote; continue; }
          }catch(problem){ SYNC.error=problem.message; }
        }else{ SYNC.error=e.message; }
        if(e.status===401){ API.on=false; await enterDemo(); }
        break;
      }
    }
  })();
  try{ await SYNC.running; }finally{ SYNC.running=null; paintSession(); }
}
function resolveSync(choice){
  if(!SYNC.conflict) return;
  const remote=SYNC.conflict.remote, merged=mergeThree(SYNC.base,payloadState(S),remote,choice);
  Object.assign(S,merged.state); SYNC.base=remote; SYNC.conflict=null; save(); render(); flushSync();
}
window.addEventListener("online",async()=>{
  if(SPACE==="private" && await API.probe(true)){ SYNC.dirty=true; flushSync(); }
});

/* 后端。有就用，没有就当它不存在——整个应用在纯本地下必须一样能跑。

   探测只做一次，失败就永久关掉，不重试、不轮询。一个连不上的后端不该
   让每个页面都卡半秒。 */
const API = {
  on: false, tried: false, base: "", why: "",
  health: null,

  async probe(){
    if(this.tried) return this.on;
    this.tried = true;
    // 只在自己这个源上找。跨源的后端连不上，也不该去猜别人的地址。
    try{
      const r = await fetch("/api/health", { method:"GET", cache:"no-store" });
      if(!r.ok) throw new Error("HTTP " + r.status);
      const h = await r.json();
      if(!h || h.fmt !== "yang.jsonl") throw new Error("这不是养想法的后端");
      this.on = true; this.health = h;
    }catch(e){
      this.on = false;
      this.why = String(e && e.message || e);
    }
    return this.on;
  },

  async _get(p){
    const r = await fetch(p, { cache:"no-store" });
    const j = await r.json().catch(()=>null);
    if(!r.ok) throw new Error((j && j.error) || ("HTTP " + r.status));
    return j;
  },
  async _post(p, body){
    const r = await fetch(p, { method:"POST", cache:"no-store",
      headers:{ "Content-Type":"application/json" },
      body: JSON.stringify(body === undefined ? null : body) });
    const j = await r.json().catch(()=>null);
    if(!r.ok) throw new Error((j && j.error) || ("HTTP " + r.status));
    return j;
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

/* 推送做防抖。每答一句就发一次全量，在几十个想法的规模上是够用的，
   而且比增量同步少一整类「两边不一致」的 bug。真长到几百个再说。 */
let pushT = null, pushing = false;
function syncUp(){
  if(!API.on) return;
  clearTimeout(pushT);
  pushT = setTimeout(async ()=>{
    if(pushing) return;
    pushing = true;
    try{ await API.push(S, "merge"); }
    catch(e){ API.why = String(e && e.message || e); }
    pushing = false;
  }, 900);
}

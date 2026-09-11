/* ===== 本地库：IndexedDB 是长住的地方，localStorage 只是一份能秒开的镜像 ===== */
const DB = { name:"yang", ver:2, h:null, ok:false, why:"还没连上" };
function idbReq(r){ return new Promise((res,rej)=>{ r.onsuccess=()=>res(r.result); r.onerror=()=>rej(r.error); }); }
function idbOpen(){
  return new Promise((res,rej)=>{
    if(!globalThis.indexedDB) return rej(new Error("这个浏览器没给 IndexedDB"));
    let rq; try{ rq = indexedDB.open(DB.name, DB.ver); }catch(e){ return rej(e); }
    rq.onupgradeneeded = ()=>{ const d=rq.result;
      if(!d.objectStoreNames.contains("ideas")) d.createObjectStore("ideas",{keyPath:"id"});
      if(!d.objectStoreNames.contains("sparks")) d.createObjectStore("sparks",{keyPath:"id"});
      if(!d.objectStoreNames.contains("cold"))  d.createObjectStore("cold",{keyPath:"id"});
      if(!d.objectStoreNames.contains("kv"))    d.createObjectStore("kv",{keyPath:"k"}); };
    rq.onsuccess = ()=>res(rq.result);
    rq.onerror   = ()=>rej(rq.error || new Error("打不开"));
    rq.onblocked = ()=>rej(new Error("另一个标签页占着旧版本"));
    setTimeout(()=>rej(new Error("等太久了")), 4000);
  });
}
async function dbRead(){
  const tx = DB.h.transaction(["ideas","sparks","cold","kv"],"readonly");
  const ideas = await idbReq(tx.objectStore("ideas").getAll());
  const sparks= await idbReq(tx.objectStore("sparks").getAll());
  const cold  = await idbReq(tx.objectStore("cold").getAll());
  const kv    = await idbReq(tx.objectStore("kv").getAll());
  const m = {}; kv.forEach(x=>m[x.k]=x.v);
  return { ideas, sparks, cold, conf:m.conf||null };
}
function dbWrite(){
  if(!DB.ok) return Promise.resolve();
  return new Promise((res)=>{
    let tx; try{ tx = DB.h.transaction(["ideas","sparks","cold","kv"],"readwrite"); }catch(e){ DB.ok=false; DB.why="写的时候断了"; return res(); }
    tx.oncomplete=()=>res(); tx.onerror=()=>{ DB.ok=false; DB.why="写失败了"; res(); };
    const a=tx.objectStore("ideas"), sp=tx.objectStore("sparks"), b=tx.objectStore("cold"), k=tx.objectStore("kv");
    a.clear(); sp.clear(); b.clear();
    S.ideas.forEach(i=>a.put(JSON.parse(JSON.stringify(i))));
    (S.sparks||[]).forEach(x=>sp.put(JSON.parse(JSON.stringify(x))));
    S.cold.forEach(c=>b.put(JSON.parse(JSON.stringify(c))));
    k.put({k:"conf", v:JSON.parse(JSON.stringify(S.conf||defaultConf()))});
    k.put({k:"meta", v:{ ver:YD.V, at:Date.now() }});
  });
}
let wTimer=null;
function save(){
  try{ localStorage.setItem(LS, JSON.stringify(S)); }catch(e){}
  if(typeof syncUp === "function") syncUp();
  if(DB.ok){ clearTimeout(wTimer); wTimer=setTimeout(dbWrite, 250); }
}
async function dbBoot(){
  try{ DB.h = await idbOpen(); DB.ok = true; DB.why=""; }
  catch(e){ DB.ok=false; DB.why=String(e && e.message || e); return null; }
  try{ return await dbRead(); }
  catch(e){ DB.ok=false; DB.why="读不出来："+String(e && e.message || e); return null; }
}


/* ================== 导航 ================== */
const VIEWS = ["today","list","one","stars","data","new","why"];
const NAVED = { today:1, list:1, stars:1, data:1 };
function render(){
  ({ today:vToday, list:vList, one:vOne, stars:vStars, data:renderData, new:vNew, why:vWhy })[S.v]();
}
function go(v,id){
  stopLive(); voiceStop();
  if(v!=="one") live=null, forks=null;
  S.v=v; if(id!==undefined) S.cur=id; save();
  VIEWS.forEach(k=>document.getElementById("v-"+k).classList.toggle("on",k===v));
  document.querySelectorAll(".nav button").forEach(b=>
    b.setAttribute("aria-selected", String(b.dataset.v===v)));
  document.getElementById("nav").style.display = NAVED[v] ? "" : "none";
  document.getElementById("fab").style.display = (v==="data"||v==="one"||v==="new"||v==="why") ? "none" : "";
  render();
  window.scrollTo(0,0);
}
function back(host,text,fn){
  const b=el("button","back","← "+text); b.type="button";
  b.addEventListener("click",fn); host.appendChild(b); return b;
}
function empty(host,msg,btn,fn){
  const e=el("div","empty"); e.appendChild(el("p",null,msg));
  if(btn){ const b=el("button","btn",btn); b.type="button"; b.addEventListener("click",fn); e.appendChild(b); }
  host.appendChild(e);
}
function modelName(kind){
  const c=S.conf||{}, id=(c.route||{})[kind];
  const m=(c.models||[]).find(x=>x.id===id);
  return m ? m.name : "Claude";
}

/* ================== 今天 ================== */
let picking=false;
function vToday(){
  const r=document.getElementById("v-today"); r.textContent="";
  r.appendChild(el("h1","big d","今天动哪一个"));
  if(!S.ideas.length){
    r.appendChild(el("p","lede","还没有在养的想法。"));
    empty(r,"先随手记一句。不用想清楚，\n想清楚是后面的事。","记一个念头",()=>go("new"));
    if(S.sparks.length) r.appendChild(sparkRow());
    return;
  }
  r.appendChild(el("p","lede","你在养 "+S.ideas.length+" 个。答一句，就算长了一回。"));

  if(!S.today || S.today.day!==today() || !S.ideas.some(i=>i.id===S.today.id)){
    const o=S.ideas.slice().sort((a,b)=>lastAt(a)-lastAt(b))[0];
    S.today={ day:today(), id:o.id, by:"local",
      why: o.grew.length
        ? ("它停得最久，"+ago(lastAt(o))+"没动过。上一句停在「"+
           String(o.grew[o.grew.length-1].q).slice(0,18)+"…」")
        : "它还一次都没长过。" };
    save();
  }
  const t=S.today, it=S.ideas.find(i=>i.id===t.id);
  const c=el("div","slip big2");
  c.appendChild(el("p","tag", picking ? "正在挑…" : (it.grew.length ? "停在半路" : "还没长过")));
  c.appendChild(el("h3",null,it.title));
  c.appendChild(el("p","why", picking ? "" : (t.why||"")));
  const row=el("div","prow");
  const a=el("button","main","接着答"); a.type="button";
  a.addEventListener("click",()=>{ go("one",it.id); setTimeout(()=>draw("ask",cur()),80); });
  const b=el("button",null,"打开它"); b.type="button";
  b.addEventListener("click",()=>go("one",it.id));
  const d=el("button",null,"换一个"); d.type="button";
  d.addEventListener("click",()=>{
    const rest=S.ideas.filter(i=>i.id!==t.id);
    if(!rest.length) return;
    const o=rest.sort((x,y)=>lastAt(x)-lastAt(y))[0];
    S.today={ day:today(), id:o.id, by:"local",
      why: o.grew.length ? ("它排在下一个，"+ago(lastAt(o))+"没动过。") : "它还一次都没长过。" };
    save(); vToday();
  });
  row.appendChild(a); row.appendChild(b); row.appendChild(d);
  c.appendChild(row);
  if(AI && S.ideas.length>1){
    const ab=el("button","tinybtn", picking ? "正在读你写的…" : "让它替我挑"); ab.type="button";
    ab.disabled=picking;
    ab.addEventListener("click",async ()=>{
      picking=true; vToday();
      let p=null; try{ p=await agPick(); }catch(e){}
      picking=false;
      if(p){ S.today={ day:today(), id:p.id, why:p.why, by:"ai" }; save(); }
      if(S.v==="today") vToday();
    });
    c.appendChild(ab);
  }
  r.appendChild(c);

  const rest=S.ideas.filter(i=>i.id!==S.today.id)
    .sort((a,b)=>lastAt(b)-lastAt(a)).slice(0,3);
  if(rest.length){
    r.appendChild(hsec("还醒着"));
    rest.forEach(i=>r.appendChild(miniRow(i)));
  }
  if(S.sparks.length) r.appendChild(sparkRow());
  r.appendChild(foot());
}
function hsec(t){ const d=el("div","hsec"); d.appendChild(el("span",null,t)); return d; }
function miniRow(i){
  const w=el("div","mini"); w.tabIndex=0;
  const open=()=>go("one",i.id);
  w.addEventListener("click",open);
  w.addEventListener("keydown",e=>{ if(e.key==="Enter") open(); });
  const l=el("div","l");
  l.appendChild(el("p","t d",i.title));
  l.appendChild(el("p","m",(i.grew.length?("长了 "+i.grew.length+" 回 · "):"还没长过 · ")+ago(lastAt(i))));
  w.appendChild(l); w.appendChild(rings(i.grew.length));
  return w;
}
function rings(n){
  const w=el("span","rings");
  for(let k=0;k<Math.min(n,5);k++) w.appendChild(el("i"));
  if(!n) w.appendChild(el("i","hollow"));
  return w;
}
function sparkRow(){
  const w=el("div","mini dash"); w.tabIndex=0;
  const open=()=>{ S.tab="spark"; go("list"); };
  w.addEventListener("click",open);
  w.addEventListener("keydown",e=>{ if(e.key==="Enter") open(); });
  const l=el("div","l");
  l.appendChild(el("p","t",S.sparks.length+" 个念头没整理"));
  const old=S.sparks.slice().sort((a,b)=>a.at-b.at)[0];
  l.appendChild(el("p","m","最早那条放了 "+ago(old.at).replace("前","")));
  w.appendChild(l); w.appendChild(el("span","chev","›"));
  return w;
}

/* ================== 想法 / 念头 / 凉了的 ================== */
function vList(){
  const r=document.getElementById("v-list"); r.textContent="";
  const tabs=el("div","subtabs");
  [["live","在养",S.ideas.length],["spark","念头",S.sparks.length],["cold","凉了的",S.cold.length]]
    .forEach(([k,n,c])=>{
      const b=el("button"); b.type="button"; b.setAttribute("aria-selected",String(S.tab===k));
      b.appendChild(document.createTextNode(n));
      if(c) b.appendChild(el("span","n"," "+c));
      b.addEventListener("click",()=>{ S.tab=k; save(); vList(); window.scrollTo(0,0); });
      tabs.appendChild(b);
    });
  r.appendChild(tabs);
  if(S.tab==="live") listLive(r);
  else if(S.tab==="spark") listSpark(r);
  else listCold(r);
}
function listLive(r){
  if(!S.ideas.length) return empty(r,"还没有在养的想法。\n先记一个念头，再决定养不养。","记一个念头",()=>go("new"));
  r.appendChild(el("p","lede","一个想法不是一次想清楚的，是被追问出来的。点进去，让它长。"));
  S.ideas.slice().sort((a,b)=>lastAt(b)-lastAt(a)).forEach(i=>{
    const s=el("div","slip"); s.tabIndex=0;
    const open=()=>go("one",i.id);
    s.addEventListener("click",open);
    s.addEventListener("keydown",e=>{ if(e.key==="Enter") open(); });
    s.appendChild(el("h3",null,i.title));
    const n=(i.now||"").trim();
    s.appendChild(el("p","now"+(n?"":" none"), n || (i.seed||"还只有最初那一句。")));
    const m=el("div","meta");
    m.appendChild(rings(i.grew.length));
    m.appendChild(el("span",null,(i.grew.length?("长了 "+i.grew.length+" 回"):"还没长过")+" · "+ago(lastAt(i))));
    s.appendChild(m);
    r.appendChild(s);
  });
  r.appendChild(foot());
}
let shaping=null;
function listSpark(r){
  const box=el("div","sheet");
  box.appendChild(el("p","lab","刚想到什么？"));
  const ta=document.createElement("textarea"); ta.rows=2;
  ta.placeholder="一句话就行。不用想清楚，成不成以后再说。";
  box.appendChild(speakable(ta));
  const row=el("div","prow");
  const ok=el("button","main","记下来"); ok.type="button";
  ok.addEventListener("click",()=>{
    const v=ta.value.trim(); if(!v){ ta.focus(); return; }
    S.sparks.unshift({ id:uid("k"), text:v.slice(0,2000), at:Date.now() });
    save(); vList();
  });
  row.appendChild(ok); box.appendChild(row);
  r.appendChild(box);

  if(!S.sparks.length){
    r.appendChild(el("p","note2","放久了的念头会自己往下沉，不会被删。沉到底还想得起来的，通常值得养。"));
    return;
  }
  r.appendChild(hsec("堆着的"));
  S.sparks.slice().sort((a,b)=>b.at-a.at).forEach(k=>{
    const w=el("div","spark");
    w.appendChild(el("p","t",k.text));
    w.appendChild(el("p","m",ago(k.at)));
    const row=el("div","prow");
    if(shaping===k.id){
      row.appendChild(el("span","tag","正在给它起个头…"));
    } else {
      const g=el("button","main2","养起来"); g.type="button";
      g.addEventListener("click",()=>grow(k));
      const d=el("button",null,"丢掉"); d.type="button";
      d.addEventListener("click",()=>{ S.sparks=S.sparks.filter(x=>x.id!==k.id); save(); vList(); });
      row.appendChild(g); row.appendChild(d);
    }
    w.appendChild(row); r.appendChild(w);
  });
  r.appendChild(el("p","note2","放久了的念头会自己往下沉，不会被删。沉到底还想得起来的，通常值得养。"));
}
async function grow(k){
  const epoch=workspaceEpoch;
  shaping=k.id; vList();
  let sh;
  try{ sh = await agShape(k.text); }
  catch(e){ sh = { title:k.text.slice(0,14), seed:k.text, first:pick(ASK,[]) }; }
  shaping=null;
  const n={ id:uid(), title:sh.title, seed:sh.seed, now:"", grew:[], created:Date.now() };
  if(epoch!==workspaceEpoch) return;
  S.ideas.unshift(n);
  S.sparks=S.sparks.filter(x=>x.id!==k.id);
  save();
  live={ kind:"ask", q:sh.first, by: AI ? modelName("ask") : "题库" };
  go("one",n.id);
}
function listCold(r){
  if(!S.cold.length) return empty(r,"还没有凉掉的想法。\n凉掉不丢人——凉掉却没留下一句话才可惜。");
  r.appendChild(el("p","lede","这里最值钱的不是想法，是每条下面那句「为什么」。"));
  const row=el("div","prow");
  const pb=el("button", patt.loading?null:"main", patt.loading?"正在翻…":"看看有没有规律"); pb.type="button";
  pb.disabled=!!patt.loading || S.cold.length<2;
  pb.addEventListener("click",doPattern);
  row.appendChild(pb);
  if(S.cold.length<2) row.appendChild(el("span","spkhint","至少两条才看得出规律"));
  r.appendChild(row);
  if(patt.text){
    const p=el("div","prompt");
    p.appendChild(el("p","kind","翻了 "+S.cold.length+" 条"));
    p.appendChild(el("p","body",patt.text));
    const pr=el("div","prow");
    const x=el("button",null,"收起来"); x.type="button";
    x.addEventListener("click",()=>{ patt.text=""; vList(); });
    pr.appendChild(x); p.appendChild(pr);
    r.appendChild(p);
  }
  if(patt.err) r.appendChild(el("p","note2",patt.err));
  S.cold.slice().sort((a,b)=>b.at-a.at).forEach(c=>{
    const w=el("div","tomb");
    w.appendChild(el("h3",null,c.title));
    w.appendChild(el("p","why2",c.why));
    const m=el("div","meta");
    m.appendChild(el("span",null,ago(c.at)));
    const b=el("button","del","捡回来"); b.type="button";
    b.addEventListener("click",()=>{
      S.ideas.unshift({ id:uid(), title:c.title, seed:c.why, now:"", grew:[], created:Date.now() });
      S.cold=S.cold.filter(x=>x.id!==c.id); save(); S.tab="live"; vList();
    });
    m.appendChild(b); w.appendChild(m);
    r.appendChild(w);
  });
}
let patt={ loading:false, text:"", err:"" };
async function doPattern(){
  patt={ loading:true, text:"", err:"" }; vList();
  try{
    const t=await agPattern();
    patt={ loading:false, text:t||"", err: t?"":"接上模型才看得出规律。现在只能自己往下翻。" };
  }catch(e){ patt={ loading:false, text:"", err:"没翻成。可能是网络。" }; }
  if(S.v==="list") vList();
}

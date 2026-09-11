/* 图谱。

   手机上不画力导向的毛线球——两百个词条节点挤在 390 像素里谁也看不懂。
   这里换成三样能读的东西：
     · 圈图      —— 想法之间已经撞出来的线（本地就有）
     · 桥        —— 一个词把两个想法的**不同维度**串起来，并且贴出两边的原话
     · 串一串    —— 挑两个八竿子打不着的，看后端能不能找出一条路
   后端不在的时候只剩第一样，并且明说少了什么。 */

let GV = { tab:"map", bridges:null, loading:"", err:"",
           pa:"", pb:"", path:null, terms:null };
let pair = { loading:false, r:null, err:"" };

async function doPair(){
  pair={ loading:true, r:null, err:"" }; vStars();
  try{ const x=await agPair(); pair={ loading:false, r:x, err: x?"":"挑不出来。" }; }
  catch(e){ pair={ loading:false, r:null, err:"没挑成。可能是网络。" }; }
  if(S.v==="stars") vStars();
}

function vStars(){
  const r = document.getElementById("v-stars"); r.textContent = "";
  r.appendChild(el("h1","big d","图谱"));

  if(S.ideas.length < 2){
    r.appendChild(el("p","lede","把想法之间的关系画出来。"));
    empty(r,"至少要有两个想法，\n这张图才有话说。","去看想法",()=>{ S.tab="live"; go("list"); });
    return;
  }

  const tabs = el("div","subtabs");
  [["map","圈图"],["bridge","桥"],["path","串一串"]].forEach(([k,n])=>{
    const b = el("button"); b.type="button";
    b.setAttribute("aria-selected", String(GV.tab===k));
    b.appendChild(document.createTextNode(n));
    b.addEventListener("click",()=>{ GV.tab=k; vStars(); window.scrollTo(0,0); });
    tabs.appendChild(b);
  });
  r.appendChild(tabs);

  if(!API.on){
    const w = el("div","mini dash"); w.style.cursor="default";
    const l = el("div","l");
    l.appendChild(el("p","t","后端没连上，只有圈图"));
    l.appendChild(el("p","m","「桥」和「串一串」要在本机跑 python3 -m yang serve"));
    w.appendChild(l); r.appendChild(w);
  }

  if(GV.tab==="map") gvMap(r);
  else if(GV.tab==="bridge") gvBridge(r);
  else gvPath(r);
}

/* ---------- 圈图 ---------- */
function gvMap(r){
  const live = S.ideas;
  r.appendChild(el("p","lede","圈越大，长得越久。只有你真的用「碰一下」撞过两个想法，中间才会有线。"));
  const W=340, H=Math.max(230, Math.min(440, 150+live.length*34));
  const NS="http://www.w3.org/2000/svg";
  const s=document.createElementNS(NS,"svg");
  s.setAttribute("viewBox","0 0 "+W+" "+H); s.setAttribute("width","100%");
  s.setAttribute("fill","none"); s.style.display="block";
  const cx=W/2, cy=H/2, R=Math.min(W,H)/2-38;
  const pts=live.map((it,i)=>{
    const t=(i+0.55)/live.length, ang=i*2.399963, rad=R*Math.sqrt(t);
    return { it, x:cx+rad*Math.cos(ang), y:cy+rad*Math.sin(ang), r:6+Math.min(it.grew.length,6)*1.7 };
  });
  const at={}; pts.forEach(p=>at[p.it.id]=p);
  let links=0;
  live.forEach(it=>(it.grew||[]).forEach(g=>{
    if(!g.with || !at[g.with] || g.with===it.id) return;
    const a=at[it.id], b=at[g.with];
    const l=document.createElementNS(NS,"path");
    l.setAttribute("d","M"+a.x.toFixed(1)+" "+a.y.toFixed(1)+"L"+b.x.toFixed(1)+" "+b.y.toFixed(1));
    l.setAttribute("stroke","var(--line2)"); l.setAttribute("stroke-width","1");
    l.setAttribute("stroke-dasharray","3 4");
    s.appendChild(l); links++;
  }));
  pts.forEach(p=>{
    const g=document.createElementNS(NS,"g"); g.style.cursor="pointer";
    g.addEventListener("click",()=>go("one",p.it.id));
    const c=document.createElementNS(NS,"circle");
    c.setAttribute("cx",p.x.toFixed(1)); c.setAttribute("cy",p.y.toFixed(1)); c.setAttribute("r",p.r.toFixed(1));
    c.setAttribute("fill","var(--grow)"); c.setAttribute("fill-opacity", p.it.grew.length?"0.15":"0.06");
    c.setAttribute("stroke","var(--grow)"); c.setAttribute("stroke-width","1");
    const d=document.createElementNS(NS,"circle");
    d.setAttribute("cx",p.x.toFixed(1)); d.setAttribute("cy",p.y.toFixed(1)); d.setAttribute("r","2.4");
    d.setAttribute("fill","var(--grow)");
    const tx=document.createElementNS(NS,"text");
    const lft=p.x<cx;
    tx.setAttribute("x",(p.x+(lft?p.r+7:-(p.r+7))).toFixed(1));
    tx.setAttribute("y",(p.y+4).toFixed(1));
    tx.setAttribute("text-anchor", lft?"start":"end");
    tx.setAttribute("font-size","11.5"); tx.setAttribute("fill","var(--ink2)");
    tx.textContent = p.it.title.length>11 ? p.it.title.slice(0,10)+"…" : p.it.title;
    g.appendChild(c); g.appendChild(d); g.appendChild(tx);
    s.appendChild(g);
  });
  const wrap=el("div","starbox"); wrap.appendChild(s); r.appendChild(wrap);
  r.appendChild(el("p","note2", live.length+" 个想法，"+links+" 条线。"+
    (links ? "" : "这张图现在是散的——说明你还没让它们互相撞过。")));

  const row=el("div","prow");
  const b=el("button", pair.loading?null:"main", pair.loading?"正在挑…":"帮我挑两个撞"); b.type="button";
  b.disabled=!!pair.loading;
  b.addEventListener("click",doPair);
  row.appendChild(b); r.appendChild(row);
  if(pair.err) r.appendChild(el("p","note2",pair.err));
  if(pair.r) pairBox(r);
}
function pairBox(r){
  const A=S.ideas.find(i=>i.id===pair.r.a), B=S.ideas.find(i=>i.id===pair.r.b);
  if(!A||!B) return;
  const p=el("div","prompt");
  p.appendChild(el("p","kind","碰一下 · "+(AI?modelName("collide"):"题库")));
  p.appendChild(el("p","pairline","「"+A.title+"」 × 「"+B.title+"」"));
  p.appendChild(el("p","q d",pair.r.q));
  const pr=el("div","prow");
  const g1=el("button","main","去「"+clip(A.title,6)+"」答"); g1.type="button";
  g1.addEventListener("click",()=>{ live={kind:"collide",q:pair.r.q,with:B.id,
    by:AI?modelName("collide"):"题库"}; pair.r=null; go("one",A.id); });
  const ag=el("button",null,"换两个"); ag.type="button";
  ag.addEventListener("click",doPair);
  const no=el("button",null,"算了"); no.type="button";
  no.addEventListener("click",()=>{ pair.r=null; vStars(); });
  pr.appendChild(g1); pr.appendChild(ag); pr.appendChild(no);
  p.appendChild(pr); r.appendChild(p);
}
function clip(s,n){ return s.length>n ? s.slice(0,n)+"…" : s; }

/* ---------- 桥 ---------- */
const DIMN = { title:"标题", seed:"最初那句", now:"现在它是什么", ask:"追问",
               angle:"换个角度", collide:"碰一下", note:"随手记",
               why:"为什么凉了", spark:"念头" };
function dimLabel(a){ return (a||[]).map(d=>DIMN[d]||d).join(" · "); }

function gvBridge(r){
  r.appendChild(el("p","lede","一个词，在这个想法里出现在一个地方，在另一个想法里出现在另一个地方。"+
    "跨得越远越值得看——尤其是一头在「为什么凉了」里。"));
  if(!API.on){
    r.appendChild(el("p","note2","这一块要后端来算。在本机跑起来之后刷新这一页。"));
    return;
  }
  const row=el("div","prow");
  const b=el("button","main", GV.loading==="bridge" ? "正在算…" : (GV.bridges?"再算一遍":"算一遍"));
  b.type="button"; b.disabled = GV.loading==="bridge";
  b.addEventListener("click",loadBridges);
  row.appendChild(b); r.appendChild(row);
  if(GV.err) r.appendChild(el("p","note2",GV.err));
  if(!GV.bridges) return;
  if(!GV.bridges.length){
    r.appendChild(el("p","note2","一条桥都没有。想法还太少，或者它们真的没关系——这也是个答案。"));
    return;
  }
  const show = GV.bridges.slice(0, GV.more || 8);
  r.appendChild(hsec(show.length+" / "+GV.bridges.length+" 条"));
  show.forEach(x=>{
    const w=el("div","bridge");
    const h=el("p","bt");
    h.appendChild(el("b",null,x.term));
    if(x.bonus>=1.7) h.appendChild(el("span","hot","一头在「为什么凉了」"));
    else if(x.bonus>1) h.appendChild(el("span","cross","跨维度"));
    w.appendChild(h);
    [["a",x.a_title,x.a_dims,x.a_say],["b",x.b_title,x.b_dims,x.b_say]].forEach(([k,t,dims,say])=>{
      const s=el("div","side");
      s.appendChild(el("p","st",t));
      s.appendChild(el("p","sd",dimLabel(dims)));
      if(say && say.text) s.appendChild(el("p","sq",say.text));
      s.addEventListener("click",()=>{ const id=x[k];
        if(S.ideas.some(i=>i.id===id)) go("one",id);
        else { S.tab = S.cold.some(c=>c.id===id) ? "cold" : "spark"; go("list"); } });
      w.appendChild(s);
    });
    r.appendChild(w);
  });
  if(GV.bridges.length > show.length){
    const more=el("div","prow");
    const mb=el("button",null,"再看 8 条"); mb.type="button";
    mb.addEventListener("click",()=>{ GV.more=(GV.more||8)+8; vStars(); });
    more.appendChild(mb); r.appendChild(more);
    r.appendChild(el("p","note2","越往下越弱。前几条看不出东西，后面通常也没有。"));
  }
}
async function loadBridges(){
  GV.loading="bridge"; GV.err=""; GV.more=8; vStars();
  try{ const j=await API.bridges(24); GV.bridges=j.bridges; }
  catch(e){ GV.err="没算成："+String(e&&e.message||e); GV.bridges=null; }
  GV.loading=""; if(S.v==="stars") vStars();
}

/* ---------- 串一串 ---------- */
function gvPath(r){
  r.appendChild(el("p","lede","挑两个看起来完全没关系的，看它们之间有没有一条由共同词条连成的路。"));
  if(!API.on){
    r.appendChild(el("p","note2","这一块要后端来算。在本机跑起来之后刷新这一页。"));
    return;
  }
  const all = S.ideas.map(i=>({id:i.id,t:i.title}))
    .concat(S.cold.map(c=>({id:c.id,t:c.title+"（凉了）"})))
    .concat(S.sparks.map(k=>({id:k.id,t:k.text.slice(0,16)+"（念头）"})));
  [["pa","从哪个"],["pb","到哪个"]].forEach(([key,lab])=>{
    const w=el("div","fld"); w.appendChild(el("label",null,lab));
    const sel=document.createElement("select");
    const o0=document.createElement("option"); o0.value=""; o0.textContent="——";
    sel.appendChild(o0);
    all.forEach(x=>{ const o=document.createElement("option");
      o.value=x.id; o.textContent=x.t; if(GV[key]===x.id) o.selected=true; sel.appendChild(o); });
    sel.addEventListener("change",()=>{ GV[key]=sel.value; GV.path=null; });
    w.appendChild(sel); r.appendChild(w);
  });
  const row=el("div","prow");
  const b=el("button","main", GV.loading==="path" ? "正在找…" : "串一串"); b.type="button";
  b.disabled = GV.loading==="path" || !GV.pa || !GV.pb || GV.pa===GV.pb;
  b.addEventListener("click",loadPath);
  row.appendChild(b); r.appendChild(row);
  if(GV.pa && GV.pa===GV.pb) r.appendChild(el("p","note2","挑两个不一样的。"));
  if(GV.err) r.appendChild(el("p","note2",GV.err));
  if(!GV.path) return;
  if(!GV.path.found){
    const p=el("div","prompt");
    p.appendChild(el("p","kind","没串起来"));
    p.appendChild(el("p","body",GV.path.why));
    r.appendChild(p); return;
  }
  const box=el("div","chain");
  box.appendChild(el("p","kind",GV.path.hops+" 跳"));
  GV.path.steps.forEach((s,i)=>{
    const n=el("div","step "+s.type);
    n.appendChild(el("span","dot",""));
    n.appendChild(el("span","lb",s.label));
    if(s.type==="idea") n.addEventListener("click",()=>{
      if(S.ideas.some(x=>x.id===s.ref)) go("one",s.ref);
    });
    box.appendChild(n);
    if(i<GV.path.steps.length-1) box.appendChild(el("div","bar"));
  });
  r.appendChild(box);
  r.appendChild(el("p","note2","中间每一个词都是真的在两边都出现过的，不是编出来的。"));
}
async function loadPath(){
  GV.loading="path"; GV.err=""; GV.path=null; vStars();
  try{ GV.path = await API.path(GV.pa, GV.pb); }
  catch(e){ GV.err="没找成："+String(e&&e.message||e); }
  GV.loading=""; if(S.v==="stars") vStars();
}

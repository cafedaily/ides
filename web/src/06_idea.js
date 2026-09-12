
/* ================== 一个想法 ================== */
let live = null;      // 当前抽到的提示 {kind,q,loading,with,by}
let redraft = null;
let forks = null;     // {loading, dirs}
let naming = false;

function vOne(){
  const r=document.getElementById("v-one"); r.textContent="";
  const it=cur(); if(!it){ go("list"); return; }
  back(r,"所有想法",()=>{ S.tab="live"; go("list"); });

  const tw=el("div","titlerow");
  const t=el("h2","title",it.title);
  t.contentEditable="true"; t.spellcheck=false;
  t.addEventListener("blur",()=>{ it.title=t.textContent.trim()||"没名字的想法"; save(); });
  tw.appendChild(t);
  if(AI){
    const nb=el("button","tiny", naming?"…":"起个名"); nb.type="button"; nb.disabled=naming;
    nb.addEventListener("click",async ()=>{
      naming=true; vOne();
      try{ const n=await agName(it); if(n){ it.title=n; save(); } }catch(e){showToast(e.message||"模型请求失败，请重试。",true);}
      naming=false; vOne();
    });
    tw.appendChild(nb);
  }
  r.appendChild(tw);

  const sd=el("p","seed");
  sd.appendChild(el("b",null,"最初那句"));
  sd.appendChild(document.createTextNode(it.seed||"（没记下来）"));
  r.appendChild(sd);

  const sh=el("div","sheet");
  sh.appendChild(el("p","lab","现在它是什么"));
  const n=(it.now||"").trim();
  const p=el("p","nowtext"+(n?"":" none"), n || "还没写。追问几次之后再回来写，会好写得多。");
  p.addEventListener("click",()=>{
    const ta=document.createElement("textarea"); ta.rows=7; ta.value=it.now||"";
    ta.placeholder="把它现在的样子写下来。可以随时推翻重写——这一块就是作品本身。";
    const w=speakable(ta);
    sh.replaceChild(w,p); ta.focus();
    ta.addEventListener("blur",()=>{ setTimeout(()=>{ if(VC.ta===ta) return;
      it.now=ta.value; save(); vOne(); },120); });
  });
  sh.appendChild(p);
  if(AI && it.grew.length>=2 && !redraft){
    const rb=el("button","tinybtn","按记录重写一遍"); rb.type="button";
    rb.addEventListener("click",()=>rewrite(it));
    sh.appendChild(rb);
  }
  r.appendChild(sh);
  if(redraft) r.appendChild(redraftBox(it));

  const acts=el("div","acts");
  mkAct(acts,"追问我","逼它具体一点",()=>draw("ask",it));
  mkAct(acts,"换个角度","把它掰弯看看",()=>draw("angle",it));
  mkAct(acts,"碰一下","塞进一个不相干的",()=>draw("collide",it));
  mkAct(acts,"分叉","从这里长出另一个",()=>doFork(it));
  r.appendChild(acts);

  if(live) r.appendChild(promptBox(it));
  if(forks) r.appendChild(forkBox(it));

  if(it.grew.length){
    r.appendChild(hsec("它是怎么长的"));
    it.grew.slice().reverse().forEach((g,idx)=>{
      const real=it.grew.length-1-idx;
      const w=el("div","item"+(g.kind==="ask"?" ask":""));
      w.appendChild(el("p","k", KIND[g.kind]+" · "+ago(g.at)+(g.by?(" · "+g.by):"")));
      w.appendChild(el("p","q", g.q));
      w.appendChild(el("p","a", g.a));
      const d=el("button","del","删掉这条"); d.type="button";
      d.addEventListener("click",()=>{ it.grew.splice(real,1); save(); vOne(); });
      w.appendChild(d);
      r.appendChild(w);
    });
  }
  const dg=el("div","danger");
  const cb=el("button",null,"这个先凉着吧"); cb.type="button";
  cb.addEventListener("click",()=>go("why",it.id));
  dg.appendChild(cb); r.appendChild(dg);
}
function mkAct(host,title,sub,fn){
  const b=el("button"); b.type="button";
  b.appendChild(el("b",null,title));
  b.appendChild(el("span",null,sub));
  b.addEventListener("click",fn);
  host.appendChild(b);
}
function focusTA(){ setTimeout(()=>{ const ta=document.querySelector(".prompt textarea"); if(ta) ta.focus(); },60); }

async function draw(kind,it){
  stopLive(); redraft=null; forks=null;
  const used=it.grew.filter(g=>g.kind===kind).map(g=>g.q);
  if(!requireModel())return;

  live={kind,q:"",loading:true}; vOne();
  const ac=new AbortController(); liveAbort=ac;
  let task, withId=null;
  if(kind==="collide"){
    const others=(S.conf.seeOthers!==false) ? S.ideas.filter(x=>x.id!==it.id && (x.now||x.seed)) : [];
    if(others.length && Math.random()<0.4){
      const o=others[Math.floor(Math.random()*others.length)]; withId=o.id;
      task="把他另一个想法「"+o.title+"」（"+String(o.now||o.seed).slice(0,140)+"）和这个撞在一起，让他找出第三个东西。";
    } else {
      task="拿「"+pick(STUFF,[])+"」这个完全不相干的东西，硬塞进这个想法里，让他看看会撞出什么。不用合理。";
    }
  } else task=TASK[kind];

  const input = "你在帮一个人养一个还没成形的想法。下面是它现在的样子。\n\n"+ideaCtx(it)+
    "\n\n你要做的："+task+"\n\n"+tone()+NOSLOP;
  try{
    const t=await say(input,{ action:kind, tier:"quick", signal:ac.signal, onText:({text})=>{
      if(liveAbort!==ac || !live || !live.loading) return;
      live.q=text;
      const q=document.querySelector(".prompt .q");
      if(q){ q.textContent=text; q.classList.remove("wait"); }
    }});
    if(liveAbort!==ac) return;
    liveAbort=null;
    if(t) live={kind,q:t,with:withId,by:modelName(kind)};
    else live={kind,error:"模型没有返回问题，请重试。"};
  }catch(e){
    if(e && e.code==="cancelled") return;
    if(liveAbort!==ac) return;
    liveAbort=null;
    live={kind,error:e.message||"模型请求失败，请重试。"};
  }
  vOne(); focusTA();
}
function promptBox(it){
  const box=el("div","prompt");
  if(live.error){
    const message=el("p","error-message",live.error);message.setAttribute("role","alert");box.appendChild(message);
    const retry=el("button","main","重试");retry.onclick=()=>draw(live.kind,it);box.appendChild(retry);
    const config=el("button","secondary","检查模型配置");config.onclick=()=>{settingsTab="models";go("data");};box.appendChild(config);return box;
  }
  box.appendChild(el("p","kind", KIND[live.kind] + (live.loading ? " · 正在读你写的" : (live.by?(" · "+live.by):""))));
  const qp=el("p","q d"+(live.loading&&!live.q?" wait":""), live.q||"");
  box.appendChild(qp);
  if(live.loading){
    const row=el("div","prow");
    const no=el("button",null,"算了"); no.type="button";
    no.addEventListener("click",()=>{ stopLive(); live=null; vOne(); });
    row.appendChild(no); box.appendChild(row);
    return box;
  }
  const ta=document.createElement("textarea"); ta.rows=4;
  ta.placeholder="想到什么写什么，写歪了也算数。";
  box.appendChild(speakable(ta));
  const row=el("div","prow");
  const ok=el("button","main","记下来"); ok.type="button";
  ok.addEventListener("click",()=>{
    const v=ta.value.trim(); if(!v){ ta.focus(); return; }
    const rec={kind:live.kind,q:live.q,a:v,at:Date.now(),by:live.by||""};
    if(live.with) rec.with=live.with;
    it.grew.push(rec); live=null; voiceStop(); save(); vOne();
  });
  const again=el("button",null,"换一个"); again.type="button";
  again.addEventListener("click",()=>draw(live.kind,it));
  const no=el("button",null,"算了"); no.type="button";
  no.addEventListener("click",()=>{ live=null; voiceStop(); vOne(); });
  row.appendChild(ok); row.appendChild(again); row.appendChild(no);
  box.appendChild(row);
  return box;
}

/* 分叉 */
async function doFork(it){
  if(!requireModel())return;
  const epoch=workspaceEpoch;
  stopLive(); live=null; redraft=null;
  forks={ loading:true, dirs:null }; vOne();
  let d=null;
  try{ d=await agFork(it); }catch(e){showToast(e.message||"模型请求失败，请重试。",true);}
  if(epoch!==workspaceEpoch) return;
  forks={ loading:false, dirs:d };
  if(S.v==="one") vOne();
}
function forkBox(it){
  const box=el("div","prompt");
  box.appendChild(el("p","kind", forks.loading ? "分叉 · 正在想三个方向" : "分叉"));
  if(forks.loading){ box.appendChild(el("p","q d wait","")); }
  else if(!forks.dirs || !forks.dirs.length){
    box.appendChild(el("p","q d","这回没想出来。"));
    box.appendChild(el("p","hint","直接分一个空的出去也行，名字自己改。"));
  } else {
    forks.dirs.forEach(d=>{
      const w=el("div","fork");
      w.appendChild(el("p","t d",d.title));
      w.appendChild(el("p","w",d.why));
      const b=el("button","main2","分这个"); b.type="button";
      b.addEventListener("click",()=>{
        const n={ id:uid(), title:d.title, seed:"从「"+it.title+"」分出来的："+d.why,
                  now:it.now||"", grew:[], created:Date.now() };
        S.ideas.unshift(n); forks=null; save(); go("one",n.id);
      });
      w.appendChild(b); box.appendChild(w);
    });
  }
  const row=el("div","prow");
  if(!forks.loading){
    const s=el("button",null,"分一个空的"); s.type="button";
    s.addEventListener("click",()=>{
      const n={ id:uid(), title:it.title+"（另一支）", seed:"从「"+it.title+"」分出来的。",
                now:it.now||"", grew:[], created:Date.now() };
      S.ideas.unshift(n); forks=null; save(); go("one",n.id);
    });
    row.appendChild(s);
  }
  const x=el("button",null,"算了"); x.type="button";
  x.addEventListener("click",()=>{ forks=null; vOne(); });
  row.appendChild(x); box.appendChild(row);
  return box;
}

/* 按记录重写 */
async function rewrite(it){
  const epoch=workspaceEpoch;
  stopLive(); live=null; forks=null;
  redraft={loading:true,text:""}; vOne();
  const ac=new AbortController(); liveAbort=ac;
  const input = "下面是一个人正在养的一个想法，以及他被追问时自己给出的回答。\n\n"+ideaCtx(it)+
    "\n\n把这些揉成一段：这个想法现在到底是什么。只能用他答里已经出现过的东西，"+
    "不要替他添任何他没说过的功能、市场、口号。三到六句，中文，平静地陈述，不要标题、不要分点、不要夸它。";
  try{
    const t=await say(input,{ tier:"default", signal:ac.signal, onText:({text})=>{
      if(liveAbort!==ac || !redraft) return;
      redraft.text=text;
      const x=document.getElementById("rdta"); if(x) x.value=text;
    }});
    if(liveAbort!==ac) return;
    liveAbort=null;
    redraft = t ? {loading:false,text:t} : {loading:false,fail:true,text:""};
  }catch(e){
    if(e && e.code==="cancelled") return;
    if(liveAbort!==ac) return;
    liveAbort=null; redraft={loading:false,fail:true,text:""};
  }
  if(S.v==="one") vOne();
}
function redraftBox(it){
  const box=el("div","prompt");
  box.appendChild(el("p","kind", redraft.loading ? "正在按记录重写" : "按记录重写"));
  if(redraft.fail){
    box.appendChild(el("p","q d","这回没写成。"));
    box.appendChild(el("p","hint","可能是网络，也可能是它这会儿不想说话。你自己那一版一个字没动。"));
    const row=el("div","prow");
    const rt=el("button","main","再试一次"); rt.type="button";
    rt.addEventListener("click",()=>rewrite(it));
    const no=el("button",null,"算了"); no.type="button";
    no.addEventListener("click",()=>{ redraft=null; vOne(); });
    row.appendChild(rt); row.appendChild(no); box.appendChild(row);
    return box;
  }
  const ta=document.createElement("textarea"); ta.rows=8; ta.id="rdta";
  ta.value=redraft.text||""; ta.placeholder="…";
  box.appendChild(ta);
  box.appendChild(el("p","hint","这只是一版草稿，用的全是你自己答过的话。改到像你说的，再换。"));
  const row=el("div","prow");
  if(!redraft.loading){
    const ok=el("button","main","换成这段"); ok.type="button";
    ok.addEventListener("click",()=>{
      const v=ta.value.trim(); if(!v){ ta.focus(); return; }
      it.now=v; redraft=null; save(); vOne();
    });
    const ag=el("button",null,"再写一版"); ag.type="button";
    ag.addEventListener("click",()=>rewrite(it));
    row.appendChild(ok); row.appendChild(ag);
  }
  const no=el("button",null,redraft.loading?"算了":"不要"); no.type="button";
  no.addEventListener("click",()=>{ stopLive(); redraft=null; vOne(); });
  row.appendChild(no); box.appendChild(row);
  return box;
}

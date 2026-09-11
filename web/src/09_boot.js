
/* ================== 记一个念头 ================== */
function vNew(){
  const r=document.getElementById("v-new"); r.textContent="";
  back(r,"回去",()=>go(S.v==="new" ? "today" : S.v));
  r.appendChild(el("h1","big d","记一个念头"));
  r.appendChild(el("p","lede","不用想清楚。一句话，甚至半句，先放进来。"));
  const box=el("div","sheet");
  const ta=document.createElement("textarea"); ta.rows=5;
  ta.placeholder="如果……／为什么没有人……／要是把 A 和 B 放一起……";
  box.appendChild(speakable(ta));
  const row=el("div","prow");
  const ok=el("button","main","放进念头堆"); ok.type="button";
  ok.addEventListener("click",()=>{
    const v=ta.value.trim(); if(!v){ ta.focus(); return; }
    S.sparks.unshift({ id:uid("k"), text:v.slice(0,2000), at:Date.now() });
    voiceStop(); save(); S.tab="spark"; go("list");
  });
  const now=el("button",null,"直接开始养"); now.type="button";
  now.addEventListener("click",async ()=>{
    const v=ta.value.trim(); if(!v){ ta.focus(); return; }
    voiceStop();
    const k={ id:uid("k"), text:v.slice(0,2000), at:Date.now() };
    S.sparks.unshift(k); save();
    S.tab="spark"; go("list"); grow(k);
  });
  row.appendChild(ok); row.appendChild(now);
  box.appendChild(row);
  r.appendChild(box);
  r.appendChild(el("p","note2","「放进念头堆」是先存着；「直接开始养」会立刻给它起个名字，"+
    "并且问你第一个问题。"));
  setTimeout(()=>ta.focus(),80);
}

/* ================== 凉之前 ================== */
let chilling={ loading:false, push:"", asked:false };
function vWhy(){
  const r=document.getElementById("v-why"); r.textContent="";
  const it=cur(); if(!it){ go("list"); return; }
  back(r,"算了，继续养",()=>{ chilling={loading:false,push:"",asked:false}; go("one",it.id); });
  r.appendChild(el("h1","big d","为什么凉了？"));
  r.appendChild(el("p","lede","这一句最值钱。想法凉掉不可惜，凉掉却没留下一句话才可惜。"));
  const box=el("div","sheet");
  const ta=document.createElement("textarea"); ta.rows=5; ta.id="whyta";
  ta.placeholder="想着想着发现…／其实我真正想要的是…／它挺好的，但不是现在。";
  box.appendChild(speakable(ta));
  const row=el("div","prow");
  const ok=el("button","main","放进「凉了的」"); ok.type="button";
  ok.addEventListener("click",()=>finishChill(it,ta));
  row.appendChild(ok);
  if(AI && !chilling.asked){
    const pb=el("button",null, chilling.loading?"…":"先让它问我一句"); pb.type="button";
    pb.disabled=!!chilling.loading;
    pb.addEventListener("click",async ()=>{
      const v=ta.value.trim(); if(!v){ ta.focus(); return; }
      chilling={loading:true,push:"",asked:false}; vWhy();
      document.getElementById("whyta").value=v;
      let t=null; try{ t=await agChill(it,v); }catch(e){}
      chilling={loading:false,push:t||"",asked:true};
      if(S.v==="why"){ vWhy(); const x=document.getElementById("whyta"); if(x) x.value=v; }
    });
    row.appendChild(pb);
  }
  box.appendChild(row);
  r.appendChild(box);
  if(chilling.loading) r.appendChild(el("p","note2","正在读你写的…"));
  if(chilling.push){
    const p=el("div","prompt");
    p.appendChild(el("p","kind","它想问你一句"));
    p.appendChild(el("p","q d",chilling.push));
    p.appendChild(el("p","hint","答不上来也没关系。答得上来，就把上面那段改一改再收。"));
    r.appendChild(p);
  }
  setTimeout(()=>{ const x=document.getElementById("whyta"); if(x && !x.value) x.focus(); },80);
}
function finishChill(it,ta){
  const v=ta.value.trim(); if(!v){ ta.focus(); return; }
  voiceStop();
  S.cold.unshift({ id:uid("c"), title:it.title, why:v.slice(0,20000), at:Date.now() });
  S.ideas=S.ideas.filter(x=>x.id!==it.id);
  if(S.today && S.today.id===it.id) S.today=null;
  chilling={loading:false,push:"",asked:false};
  live=null; save(); S.tab="cold"; go("list");
}

function foot(){
  const f=el("div","foot");
  f.appendChild(document.createTextNode(
    API.on ? "本机的库里有一份，浏览器里也有一份。" : "存在你这台设备的浏览器里，不上传。"));
  f.appendChild(document.createElement("br"));
  const b=el("button",null,"导出、导入、模型 →"); b.type="button";
  b.addEventListener("click",()=>go("data"));
  f.appendChild(b);
  return f;
}

/* ================== 启动 ================== */
(function buildNav(){
  const nv=document.getElementById("nav");
  [["today","今天","today"],["list","想法","ideas"],["stars","图谱","stars"],["data","数据","data"]]
    .forEach(([k,n,ic])=>{
      const b=el("button"); b.type="button"; b.dataset.v=k; b.setAttribute("aria-selected","false");
      b.appendChild(svgIcon(IC[ic],21)); b.appendChild(el("span",null,n));
      b.addEventListener("click",()=>go(k));
      nv.appendChild(b);
    });
})();
document.getElementById("fab").addEventListener("click",()=>go("new"));

(async function boot(){
  let seedOnly = false;          // 这一次打开是不是只有演示种子——它不该被推给后端
  const fromDb = await dbBoot();
  if(FRESH){
    if(fromDb && (fromDb.ideas.length || fromDb.cold.length || fromDb.sparks.length)){
      S.ideas=fromDb.ideas; S.cold=fromDb.cold; S.sparks=fromDb.sparks||[];
      S.conf=fromDb.conf||defaultConf();
    } else { S = seedState(); seedOnly = true; }
    save();
  } else if(DB.ok) dbWrite();
  if(VIEWS.indexOf(S.v)<0 || (S.v==="one" && !cur())) S.v="today";
  if(S.v==="new"||S.v==="why") S.v="today";
  go(S.v);

  /* 后端是可选的。探测失败就当它不存在，整个应用照常跑。
     先拉后端的（本机那份库是权威），拉不到就用本地的，然后把本地的推上去。 */
  if(await API.probe()){
    try{
      const st = await API.pull();
      const local = (S.ideas.length + S.sparks.length + S.cold.length);
      const remote = ((st.ideas||[]).length + (st.sparks||[]).length + (st.cold||[]).length);
      if(remote){
        /* 本机那份库是权威。这边只有演示种子的话，直接换成后端的——
           别把示例数据混进他真正的想法里。 */
        const mode = seedOnly ? "replace" : "merge";
        const out = YD.apply({ideas:S.ideas, sparks:S.sparks, cold:S.cold, conf:S.conf},
          YD.records({ideas:st.ideas||[], sparks:st.sparks||[], cold:st.cold||[], conf:null}),
          mode);
        S.ideas=out.ideas; S.sparks=out.sparks||[]; S.cold=out.cold;
        if(st.conf) S.conf = Object.assign(defaultConf(), st.conf);
        save();
        if(seedOnly) return render();          // 两边一样，不用再推回去
      }
      if(local && !seedOnly) syncUp();
      render();
    }catch(e){ API.why = String(e && e.message || e); }
  }
})();

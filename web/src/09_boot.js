
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
    SPACE==="private" ? "私有空间。修改先保存在浏览器，再同步到服务端。" : "演示内容存在当前浏览器，不上传。"));
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

let workspaceEpoch=0;
function paintSession(){
  const host=document.getElementById("session-status"); if(!host) return;
  host.textContent="";
  const text=SPACE==="private" ? (SYNC.error || (SYNC.conflict ? "发现同步冲突，本机修改已保留" : SYNC.dirty || SYNC.running ? "正在保存修改" : "已登录 · 已保存")) : "本地演示 · 登录后进入自己的空间";
  host.appendChild(el("span",null,text));
  if(SPACE==="private"){
    const retry=el("button",null,"重试同步"); retry.onclick=()=>{SYNC.error="";syncUp();};
    if(SYNC.error) host.appendChild(retry);
    const out=el("button",null,"退出登录"); out.onclick=async()=>{
      await flushSync();
      try{ await API._post("/api/logout",{}); API.on=false; await enterDemo(); }
      catch(e){ SYNC.error="退出失败，请重试："+e.message; paintSession(); }
    }; host.appendChild(out);
    if(SYNC.conflict){
      host.appendChild(el("span",null,"冲突项："+SYNC.conflict.conflicts.join("、")));
      for(const [choice,label] of [["local","冲突项保留本机版本"],["remote","冲突项保留服务端版本"]]){
        const b=el("button",null,label); b.onclick=()=>resolveSync(choice); host.appendChild(b);
      }
    }
  }else{
    const login=el("button",null,"登录自己的空间"); login.onclick=showLogin; host.appendChild(login);
  }
}
function showLogin(){
  const old=document.getElementById("login-dialog"); if(old) old.remove();
  const dialog=el("dialog","login-dialog"); dialog.id="login-dialog";
  const form=document.createElement("form");
  const title=el("h2",null,"登录自己的空间"); title.id="login-title";
  dialog.setAttribute("aria-labelledby",title.id); form.appendChild(title);
  form.appendChild(el("p",null,"演示数据留在当前浏览器，不会合入你的私有空间。"));
  const label=el("label",null,"访问口令"); label.htmlFor="login-token"; form.appendChild(label);
  const input=document.createElement("input"); input.id="login-token"; input.type="password"; input.autocomplete="current-password"; input.required=true; form.appendChild(input);
  const error=el("p","note"); error.setAttribute("role","alert"); form.appendChild(error);
  const submit=el("button","main","登录"); submit.type="submit"; form.appendChild(submit);
  const cancel=el("button",null,"继续演示"); cancel.type="button"; cancel.onclick=()=>dialog.close(); form.appendChild(cancel);
  form.onsubmit=async event=>{
    event.preventDefault(); submit.disabled=true; error.textContent="正在登录…";
    try{ await API._post("/api/login",{token:input.value}); input.value=""; API.tried=false;
      if(!await API.probe(true)) throw new Error(API.why);
      await enterPrivate(); dialog.close();
    }catch(e){ error.textContent=e.message; }finally{ submit.disabled=false; }
  };
  dialog.appendChild(form); document.body.appendChild(dialog); dialog.showModal(); input.focus();
}
async function chooseSpace(name){
  workspaceEpoch++;
  clearTimeout(wTimer); clearTimeout(pushT);
  stopLive(); AI=null; live=null; forks=null; redraft=null; S.cur=null; GV.bridges=null; GV.path=null;
  if(DB.h) DB.h.close(); DB.ok=false;
  for(const view of document.querySelectorAll(".view")) view.textContent="";
  patt={loading:false,text:"",err:""}; pair={loading:false,r:null,err:""}; chilling={loading:false,push:"",asked:false};
  SPACE=name; LS="yang."+name+".v2"; DB.name=LS;
  const cached=load();
  S=cached || (name==="demo" ? seedState() : {ideas:[],sparks:[],cold:[],conf:defaultConf(),v:"today",tab:"live",cur:null,today:null});
  const disk=await dbBoot();
  if(!cached && disk && (disk.ideas.length || disk.sparks.length || disk.cold.length)) Object.assign(S,disk);
  S.conf=Object.assign(defaultConf(),S.conf||{});
  S.v="today"; S.cur=null;
}
async function enterDemo(){
  if(SPACE==="private"){
    try{ S.syncBase=SYNC.base; localStorage.setItem(LS,JSON.stringify(safeState(S))); }catch(e){}
    await dbWrite();
  }
  SYNC.base=null; SYNC.conflict=null; SYNC.dirty=false;
  await chooseSpace("demo"); save(); go("today"); paintSession();
}
async function enterPrivate(){
  const remote=await API.pull();
  await chooseSpace("private");
  if(S.syncBase){
    const merged=mergeThree(S.syncBase,payloadState(S),remote);
    if(merged.conflicts.length){ SYNC.base=S.syncBase; SYNC.conflict={remote,conflicts:merged.conflicts}; }
    else{ Object.assign(S,merged.state); SYNC.base=remote; SYNC.conflict=null; }
  }else{ Object.assign(S,remote); SYNC.base=remote; SYNC.conflict=null; }
  SYNC.error=""; save(); await _initAI(); go("today"); paintSession(); await flushSync();
}
(async function boot(){
  const host=el("div","session-status"); host.id="session-status"; host.setAttribute("aria-live","polite");
  document.querySelector("header").appendChild(host);
  try{
    if(await API.probe()) await enterPrivate();
    else await enterDemo();
  }catch(e){ API.why=e.message; await enterDemo(); }
})();

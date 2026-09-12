
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
      let t=null; try{ t=await agChill(it,v); }catch(e){showToast(e.message,true);}
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
  const f=el("div","foot");f.appendChild(el("p",null,"想法保存在当前设备，随时可以导出带走。"));
  const b=el("button",null,"空间设置与数据备份");b.onclick=()=>go("data");f.appendChild(b);return f;
}
let workspaceEpoch=0;
function paintSession(){
  const host=document.getElementById("session-status");if(!host)return;host.textContent="";
  if(!S.space)return;
  const name=el("button","space-switch",S.space.name);name.onclick=()=>{settingsTab="space";go("data");};host.appendChild(name);
  const status=el("span","save-state",DB.why || (DB.pending||DB.writing?"正在保存到本机":"已保存到本机"));
  status.setAttribute("role","status");host.appendChild(status);
  if(DB.conflict){for(const [choice,label] of [["local","保留此窗口版本"],["remote","载入另一窗口版本"]]){
    const b=el("button",null,label);b.onclick=()=>resolveLocalConflict(choice);host.appendChild(b);
  }}else if(DB.why){const retry=el("button",null,"重试保存");retry.onclick=()=>dbWrite();host.appendChild(retry);}
}
function showToast(text,error=false){
  const old=document.getElementById("toast");if(old)old.remove();
  const note=el("div","toast"+(error?" error":""),text);note.id="toast";note.setAttribute("role",error?"alert":"status");
  document.body.appendChild(note);setTimeout(()=>note.remove(),7000);
}
async function switchSpace(id){
  if(hasModelDraftChanges()&&!confirm("模型配置尚未保存。放弃这些修改并切换空间？"))return;
  await dbWrite();await openLocalSpace(id);workspaceEpoch++;for(const controller of MODEL_REQUESTS)controller.abort();
  stopLive();live=null;forks=null;redraft=null;GV.bridges=null;GV.path=null;
  modelDraft=null;settingsNotice="";S.v="today";S.cur=null;_initAI();go("today");paintSession();
}
function renderWelcome(){
  document.querySelectorAll(".view").forEach(view=>view.classList.remove("on"));
  const root=document.getElementById("v-today");root.classList.add("on");root.textContent="";
  document.getElementById("nav").hidden=true;document.getElementById("fab").hidden=true;
  root.appendChild(el("p","eyebrow","一个只属于你的起点"));
  root.appendChild(el("h1","welcome-title","给想法留一个空间"));
  root.appendChild(el("p","lede","从空白开始，用你选择的模型，把一闪而过的念头慢慢养成形。"));
  const flow=el("ol","setup-flow");for(const text of ["创建自己的空间","连接自己的模型","记下第一个想法","导出备份，随时带走"])flow.appendChild(el("li",null,text));root.appendChild(flow);
  const form=el("form","welcome-form");const label=el("label",null,"空间名称");label.htmlFor="space-name";form.appendChild(label);
  const input=el("input");input.id="space-name";input.placeholder="例如：我的创作笔记";input.maxLength=60;input.required=true;input.autocomplete="off";form.appendChild(input);
  const error=el("p","error-message");error.setAttribute("role","alert");form.appendChild(error);
  const button=el("button","main","创建我的空间");button.type="submit";form.appendChild(button);
  form.onsubmit=async event=>{event.preventDefault();button.disabled=true;try{await createSpace(input.value);document.getElementById("nav").hidden=false;document.getElementById("fab").hidden=false;settingsTab="models";settingsNotice="空间已创建。接下来连接你自己的模型。";_initAI();go("data");paintSession();}catch(e){error.textContent=e.message;}finally{button.disabled=false;}};
  root.appendChild(form);root.appendChild(el("p","privacy-note","空间、想法与配置只保存在当前浏览器。只有调用模型时，相关内容才会发送给你选择的服务。"));
}
(function buildNav(){
  const nav=document.getElementById("nav");
  for(const [id,label,icon] of [["today","今天","today"],["list","想法","ideas"],["stars","图谱","stars"],["data","设置","data"]]){
    const b=el("button");b.type="button";b.dataset.v=id;b.appendChild(svgIcon(IC[icon],21));b.appendChild(el("span",null,label));b.onclick=()=>go(id);nav.appendChild(b);
  }
})();
document.getElementById("fab").onclick=()=>go("new");
(async function boot(){
  const status=el("div","session-status");status.id="session-status";document.querySelector("header").appendChild(status);
  try{
    const active=localStorage.getItem(ACTIVE_SPACE);if(active && spaceIndex.some(x=>x.id===active))await openLocalSpace(active);
    if(S.space){_initAI();go("today");paintSession();if(DB.pending)await dbWrite();}else renderWelcome();
  }catch(error){renderWelcome();showToast("读取空间失败："+error.message,true);}
})();

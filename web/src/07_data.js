/* ================== 数据 ================== */
let DL = undefined;                     // 保存文件的能力，undefined = 还没问过
let dv = { enc:false, pass:"", inText:"", inPass:"", chk:null, mode:"merge",
           out:null, busy:"", wipe:"", note:"" };

async function dlHandle(){
  if(DL !== undefined) return DL;
  DL = null;
  try{ if(window.claude && claude.use) DL = await claude.use("downloads") || null; }catch(e){ DL = null; }
  return DL;
}
function stamp(){
  const d=new Date(), z=n=>("0"+n).slice(-2);
  return d.getFullYear()+z(d.getMonth()+1)+z(d.getDate())+"-"+z(d.getHours())+z(d.getMinutes());
}
function bytes(n){ return n<1024 ? n+" B" : n<1048576 ? (n/1024).toFixed(1)+" KB" : (n/1048576).toFixed(2)+" MB"; }
function card(host,title,hint){
  const c=el("div","card");
  if(title) c.appendChild(el("h3",null,title));
  if(hint)  c.appendChild(el("p","h",hint));
  host.appendChild(c); return c;
}
function kv(host,k,v){ const r=el("div","kv"); r.appendChild(el("span",null,k));
  r.appendChild(el("span",null,v)); host.appendChild(r); return r; }
function fld(host,label,val,ph,on,note,type){
  const w=el("div","fld"); w.appendChild(el("label",null,label));
  const i=document.createElement("input"); i.type=type||"text"; i.value=val==null?"":val;
  i.id=uid("field-"); w.querySelector("label").htmlFor=i.id;
  if(ph) i.placeholder=ph;
  i.addEventListener("input",()=>on(i.value));
  w.appendChild(i);
  if(note) w.appendChild(el("p","note",note));
  host.appendChild(w); return i;
}
function chk(host,label,note,on,fn){
  const l=el("label","chk"); const i=document.createElement("input"); i.type="checkbox"; i.checked=!!on;
  i.addEventListener("change",()=>fn(i.checked));
  const t=el("div"); t.appendChild(el("b",null,label)); if(note) t.appendChild(el("span",null,note));
  l.appendChild(i); l.appendChild(t); host.appendChild(l); return i;
}
function pills(host,items,cur,fn){
  const w=el("div","pills");
  items.forEach(o=>{ const b=el("button",null,o.name); b.type="button";
    b.setAttribute("aria-pressed", String(o.k===cur));
    b.addEventListener("click",()=>fn(o.k)); w.appendChild(b); });
  host.appendChild(w); return w;
}
function rep(host,good,title,lines){
  const r=el("div","rep "+(good?"good":"bad"));
  r.appendChild(el("b",null,title));
  if(lines && lines.length){ const u=el("ul");
    lines.slice(0,20).forEach(x=>u.appendChild(el("li",null,x)));
    if(lines.length>20) u.appendChild(el("li",null,"…还有 "+(lines.length-20)+" 条，先修完这些。"));
    r.appendChild(u); }
  host.appendChild(r); return r;
}
function grewCount(){ return S.ideas.reduce((n,i)=>n+(i.grew?i.grew.length:0),0); }

function renderData(){
  if(!S.sparks) S.sparks=[];
  const r=document.getElementById("v-data"); r.textContent="";
  const b=el("button","back","← 回去"); b.type="button";
  b.addEventListener("click",()=>go("today")); r.appendChild(b);
  r.appendChild(el("h1","big d","数据"));
  r.appendChild(el("p","lede","东西全在你自己这台设备上。这一页是把它拿出来、放回去、和交给谁看的地方。"));
  if(dv.note){ rep(r,true,dv.note,null); dv.note=""; }

  /* ---- 存在哪 ---- */
  const c0=card(r,"存在哪", DB.ok
    ? "浏览器的本地数据库（IndexedDB），关掉页面也在。另存了一份能秒开的镜像。"
    : "这个浏览器现在用不了本地数据库，退到了简易存储。数据还在，但容量小、更容易被浏览器清理——尽早导一份出来。");
  kv(c0,"位置", DB.ok ? "IndexedDB · yang" : "localStorage（降级）");
  if(!DB.ok && DB.why) kv(c0,"为什么", DB.why);
  kv(c0,"在养的想法", S.ideas.length+" 个");
  kv(c0,"念头堆", (S.sparks||[]).length+" 条");
  kv(c0,"生长记录", grewCount()+" 条");
  kv(c0,"凉了的", S.cold.length+" 条");
  let raw=0; try{ raw=(localStorage.getItem(LS)||"").length; }catch(e){}
  kv(c0,"大小", bytes(raw));

  /* ---- 导出 ---- */
  const c1=card(r,"导出","JSONL：第一行是文件头，之后每行一条完整记录。坏了一行，别的还读得出来。");
  const enc=chk(c1,"用口令加密","AES-GCM-256，口令用 PBKDF2 加盐派生 21 万次。只有加密时，模型钥匙才会跟着走。",
    dv.enc,(v)=>{ dv.enc=v; dv.out=null; renderData(); });
  if(dv.enc){
    fld(c1,"口令",dv.pass,"记不住就别用——没有找回",(v)=>{dv.pass=v;},
      "忘了口令，这份文件就永远打不开了。这不是吓唬你，是 AES-GCM 的事实。","password");
  } else {
    c1.appendChild(el("p","note","不加密的话，模型钥匙不会写进文件——导入后要重新填一次。这是故意的。"));
  }
  const row1=el("div","brow");
  const eb=el("button","main", dv.busy==="export" ? "正在算签名…" : "导出"); eb.type="button";
  eb.disabled = dv.busy==="export" || (dv.enc && dv.pass.length<4);
  eb.addEventListener("click",doExport); row1.appendChild(eb);
  c1.appendChild(row1);
  if(dv.enc && dv.pass.length>0 && dv.pass.length<4)
    c1.appendChild(el("p","note","口令至少 4 个字符。"));
  if(dv.out) renderOut(c1);

  /* ---- 导入 ---- */
  const c2=card(r,"导入","先验一遍再落地。指纹对不上、少字段、id 撞车，都会在这儿告诉你是第几行。");
  const fw=el("div","fld"); fw.appendChild(el("label",null,"选一个导出文件"));
  const fi=document.createElement("input"); fi.type="file"; fi.accept=".txt,.jsonl,.json,text/plain";
  fi.addEventListener("change",()=>{
    const f=fi.files && fi.files[0]; if(!f) return;
    if(f.size > 40*1024*1024){ dv.chk={ok:false,errors:[{line:0,msg:"文件超过 40MB。"}],warnings:[]}; renderData(); return; }
    const rd=new FileReader();
    rd.onload=()=>{ dv.inText=String(rd.result||""); dv.chk=null; doCheck(); };
    rd.onerror=()=>{ dv.chk={ok:false,errors:[{line:0,msg:"读不了这个文件。"}],warnings:[]}; renderData(); };
    rd.readAsText(f);
  });
  fw.appendChild(fi); c2.appendChild(fw);
  const tw=el("div","fld"); tw.appendChild(el("label",null,"或者直接粘进来"));
  const ta=document.createElement("textarea"); ta.rows=4; ta.value=dv.inText;
  ta.placeholder='{"t":"head","fmt":"yang.jsonl",…';
  ta.addEventListener("input",()=>{ dv.inText=ta.value; dv.chk=null; });
  tw.appendChild(ta); c2.appendChild(tw);
  if(dv.chk && dv.chk.needPass)
    fld(c2,"这份是加密的，口令",dv.inPass,"",(v)=>{dv.inPass=v;},null,"password");
  const row2=el("div","brow");
  const kb=el("button",null, dv.busy==="check" ? "正在验…" : "先验一遍"); kb.type="button";
  kb.disabled = dv.busy==="check" || !dv.inText.trim();
  kb.addEventListener("click",doCheck); row2.appendChild(kb);
  c2.appendChild(row2);

  if(dv.chk) renderChk(c2);

  /* ---- 模型 ---- */
  const c3=card(r,"模型","问题由谁提出来，你说了算。这些设置会跟着导出走。");
  (S.conf.models||[]).forEach((m,i)=>renderModel(c3,m,i));
  const row3=el("div","brow");
  const ab=el("button",null,"＋ 接一个模型"); ab.type="button";
  ab.addEventListener("click",()=>{
    S.conf.models.push({ id:"m"+Math.random().toString(36).slice(2,7), name:"新的模型",
      kind:"compat", base:"https://", key:"", model:"" });
    save(); renderData();
  });
  row3.appendChild(ab); c3.appendChild(row3);
  c3.appendChild(el("p","note",
    API.on ? "模型请求通过私有服务端发送；密钥保存在服务端，浏览器不会持久保存。" : "演示模式使用本地问题。登录后可配置 OpenAI 兼容模型。"));

  const c4=card(r,"谁来问","不同动作可以选择不同模型。");
  const MS=(S.conf.models||[]).map(m=>({k:m.id,name:m.name}));
  [["name","起名字"],["ask","追问我"],["angle","换个角度"],["collide","碰一下"],["rewrite","按记录重写"]].forEach(([k,n])=>{
    const w=el("div","fld"); w.appendChild(el("label",null,n));
    pills(w,MS,S.conf.route[k],(v)=>{ S.conf.route[k]=v; save(); renderData(); });
    c4.appendChild(w);
  });
  const w1=el("div","fld"); w1.appendChild(el("label",null,"问话的口气"));
  pills(w1,[{k:"soft",name:"温和"},{k:"normal",name:"正常"},{k:"hard",name:"扎人"}],
    S.conf.sharp,(v)=>{ S.conf.sharp=v; save(); renderData(); });
  w1.appendChild(el("p","note",{soft:"顺着你的思路往下问，不拆台。",
    normal:"挑你含糊带过的那一处问。",
    hard:"专找最站不住的地方下手。答完不太舒服，但那一条通常最有用。"}[S.conf.sharp]));
  c4.appendChild(w1);
  const w2=el("div","fld"); w2.appendChild(el("label",null,"问题多长"));
  pills(w2,[{k:"one",name:"一句话"},{k:"two",name:"最多两句"}],
    S.conf.len,(v)=>{ S.conf.len=v; save(); renderData(); });
  c4.appendChild(w2);
  chk(c4,"让它读「生长记录」","知道你已经答过什么，就不会重复问。",S.conf.seeGrew,
    (v)=>{ S.conf.seeGrew=v; save(); });
  chk(c4,"让它读别的想法","「碰一下」要撞两个想法时才需要。",S.conf.seeOthers,
    (v)=>{ S.conf.seeOthers=v; save(); });

  renderGraphSettings(r);

  /* ---- 清空 ---- */
  const c5=el("div","danger2");
  c5.appendChild(el("p","h",SPACE==="private" ? "清空私有空间的数据，并同步删除服务端记录。请先导出备份。" : "清空此浏览器的演示数据。导出文件不受影响。"));
  const wf=el("div","fld");
  const wi=document.createElement("input"); wi.type="text"; wi.value=dv.wipe;
  wi.placeholder='想清空就输入「清空」两个字';
  wi.addEventListener("input",()=>{ dv.wipe=wi.value; wb.disabled = wi.value.trim()!=="清空"; });
  wf.appendChild(wi); c5.appendChild(wf);
  const row5=el("div","brow");
  const wb=el("button",null,"清空"); wb.type="button"; wb.disabled = dv.wipe.trim()!=="清空";
  wb.addEventListener("click",async ()=>{
    try{ localStorage.removeItem(LS); }catch(e){}
    S={ ideas:[], sparks:[], cold:[], conf:defaultConf(), v:"today", tab:"live", cur:null, today:null };
    await dbWrite(); save(); dv.wipe=""; go("today");
  });
  row5.appendChild(wb); c5.appendChild(row5);
  r.appendChild(c5);
}

function renderModel(host,m,i){
  const w=el("div","fld");
  w.appendChild(el("label",null,"模型 "+(i+1)));
  fld(w,"叫什么",m.name,"",(v)=>{ m.name=v; save(); });
  const kw=el("div","fld"); kw.appendChild(el("label",null,"来路"));
  const sel=document.createElement("select");
  [["claude","Claude 账号（不用配）"],["compat","OpenAI 兼容"],["ollama","本地 Ollama"],["custom","自定义"]]
    .forEach(([k,n])=>{ const o=document.createElement("option"); o.value=k; o.textContent=n;
      if(m.kind===k) o.selected=true; sel.appendChild(o); });
  sel.addEventListener("change",()=>{ m.kind=sel.value;
    if(m.kind==="ollama" && !m.base) m.base="http://localhost:11434/v1";
    save(); renderData(); });
  kw.appendChild(sel); w.appendChild(kw);
  if(m.kind!=="claude"){
    fld(w,"地址",m.base,"https://…",(v)=>{ m.base=v; save(); },
      (m.base && !/^https?:\/\//i.test(m.base)) ? "地址要以 http:// 或 https:// 开头，不然导出时会被校验拦下。" : null);
    if(m.kind!=="ollama")
      fld(w,"钥匙",m.key,"",(v)=>{ m.key=v; save(); },
        m.keyConfigured ? "服务端已保存密钥；留空会保留原密钥。" : "仅在当前页面暂存，登录后发送到服务端；不会写入浏览器存储。","password");
    if(m.keyConfigured){
      const clear=el("button",null,"清除服务端密钥"); clear.type="button";
      clear.onclick=()=>{m.clear_key=true; m.key=""; m.keyConfigured=false; save(); renderData();}; w.appendChild(clear);
    }
    fld(w,"模型名",m.model,"",(v)=>{ m.model=v; save(); });
  }
  if((S.conf.models||[]).length>1){
    const row=el("div","brow");
    const d=el("button",null,"删掉这个"); d.type="button";
    d.addEventListener("click",()=>{
      S.conf.models=S.conf.models.filter(x=>x.id!==m.id);
      const first=S.conf.models[0] && S.conf.models[0].id;
      Object.keys(S.conf.route).forEach(k=>{ if(S.conf.route[k]===m.id) S.conf.route[k]=first; });
      save(); renderData();
    });
    row.appendChild(d); w.appendChild(row);
  }
  host.appendChild(w);
}

async function doExport(){
  dv.busy="export"; dv.out=null; renderData();
  try{
    let r;
    if(API.on && SPACE==="private"){
      await flushSync();
      if(SYNC.dirty || SYNC.conflict || SYNC.error){
        r=await YD.exportJSONL(payloadState(S),{pass:dv.enc ? dv.pass : null});
        dv.note="已导出本机修改；服务端保存的密钥未包含在此离线副本中。";
      }else{
        const output=await API._post("/api/export",{pass:dv.enc ? dv.pass : null});
        r={text:output.text,encrypted:dv.enc,counts:{idea:S.ideas.length,spark:S.sparks.length,cold:S.cold.length}};
      }
    }else r=await YD.exportJSONL(payloadState(S),{pass:dv.enc ? dv.pass : null});
    const name = "养想法-"+stamp()+(r.encrypted?"-加密":"")+".jsonl.txt";
    const dl = await dlHandle();
    if(dl){
      try{
        await dl.save({ filename:name, data:r.text });
        dv.out={ kind:"ok", name:name, size:r.text.length, enc:r.encrypted, counts:r.counts };
      }catch(e){
        const code = e && e.code;
        if(code==="declined") dv.out={ kind:"info", msg:"你取消了保存。文件没写出去，数据一个字没动。" };
        else dv.out={ kind:"text", name:name, text:r.text,
          msg:"这台设备存不了文件（"+(code||"说不清")+"）。下面是全文，自己复制走。" };
      }
    } else {
      const url=URL.createObjectURL(new Blob([r.text],{type:"text/plain;charset=utf-8"}));
      const link=document.createElement("a"); link.href=url; link.download=name; document.body.appendChild(link); link.click(); link.remove();
      setTimeout(()=>URL.revokeObjectURL(url),1000);
      dv.out={kind:"ok",name,size:r.text.length,enc:r.encrypted,counts:r.counts};
    }
  }catch(e){
    dv.out={ kind:"err", msg:"导出失败："+String(e && e.message || e) };
  }
  dv.busy=""; renderData();
}

function renderOut(host){
  const o=dv.out;
  if(o.kind==="ok"){
    rep(host,true,"存好了：" + o.name,
      ["共 "+o.counts.idea+" 个想法、"+o.counts.spark+" 条念头、"+o.counts.cold+" 条凉了的，"+bytes(o.size)+"。",
       o.enc ? "已加密。口令丢了没有第二条路。" : "明文，可以直接用文本编辑器打开看。"]);
  } else if(o.kind==="info"){ rep(host,false,o.msg,null); }
  else if(o.kind==="err"){ rep(host,false,o.msg,null); }
  else {
    const box=rep(host,false,o.msg,null);
    const ta=document.createElement("textarea"); ta.rows=6; ta.value=o.text; ta.readOnly=true;
    ta.className="mono"; ta.style.width="100%"; ta.style.marginTop="10px";
    ta.style.background="var(--paper)"; ta.style.border="1px solid var(--line2)";
    ta.style.borderRadius="10px"; ta.style.padding="10px 12px";
    box.appendChild(ta);
    const row=el("div","brow");
    const cb=el("button",null,"全选"); cb.type="button";
    cb.addEventListener("click",()=>{ ta.focus(); ta.select(); });
    row.appendChild(cb); box.appendChild(row);
  }
}

async function doCheck(){
  dv.busy="check"; renderData();
  try{ dv.chk = await YD.parseJSONL(dv.inText, { pass: dv.inPass || null }); }
  catch(e){ dv.chk = { ok:false, errors:[{line:0,msg:"验的时候出错："+String(e&&e.message||e)}], warnings:[] }; }
  dv.busy=""; renderData();
}

function renderChk(host){
  const c=dv.chk;
  if(c.needPass){ rep(host,false,"这份文件是加密的，得先给口令。",null); return; }
  const errs=(c.errors||[]).map(e=> (e.line ? "第 "+e.line+" 行：" : "") + e.msg);
  if(!c.ok){ rep(host,false,"没通过，"+ (c.errors||[]).length +" 处问题。什么都没导入。",errs); return; }
  const h=c.head, lines=[];
  lines.push("导出于 "+new Date(h.at).toLocaleString()+"，格式 v"+h.v+(h.enc==="none"?"，明文":"，已加密"));
  lines.push("共 "+c.counts.idea+" 个想法、"+c.counts.spark+" 条念头、"+c.counts.cold+" 条凉了的、"+c.counts.conf+" 份配置");
  lines.push("整份指纹和每行指纹都对得上。");
  (c.warnings||[]).forEach(w=>lines.push("· "+w));
  rep(host,true,"验过了，可以导。",lines);

  const w=el("div","fld"); w.appendChild(el("label",null,"怎么放进来"));
  pills(w,[{k:"merge",name:"合并"},{k:"replace",name:"整个换掉"}],dv.mode,(v)=>{ dv.mode=v; renderData(); });
  w.appendChild(el("p","note", dv.mode==="merge"
    ? "同一个 id，谁的记录更新留谁。这台设备上独有的想法不会丢。"
    : "这台设备上现有的想法和凉了的会被文件里的整个替换掉。想清楚。"));
  host.appendChild(w);

  const row=el("div","brow");
  const ib=el("button","main","确认导入"); ib.type="button";
  ib.addEventListener("click",async ()=>{
    const out=YD.apply({ideas:S.ideas,sparks:S.sparks,cold:S.cold,conf:S.conf}, c.recs, dv.mode);
    S.ideas=out.ideas; S.sparks=out.sparks||[]; S.cold=out.cold; if(out.conf) S.conf=Object.assign(defaultConf(),out.conf);
    if(!S.conf.route) S.conf.route=defaultConf().route;
    save(); await dbWrite();
    dv.chk=null; dv.inText=""; dv.inPass=""; dv.out=null;
    dv.note="导好了：新增 "+out.report.added+" 条，更新 "+out.report.updated+
      " 条，保留本机较新的 "+out.report.kept+" 条。";
    go("today");
  });
  row.appendChild(ib); host.appendChild(row);
}

function renderGraphSettings(host){
  const settings=S.conf.graph || {};
  const box=card(host,"图谱词条","默认把 LLM、大语言模型归为大模型，并统一每一步与每步。证据保留原句。");
  const label=el("label",null,"自定义同义词（每行：别名=标准词）"); label.htmlFor="graph-aliases"; box.appendChild(label);
  const aliases=el("textarea"); aliases.id="graph-aliases"; aliases.rows=4;
  aliases.value=Object.entries(settings.aliases||{}).map(([a,b])=>a+"="+b).join("\n"); box.appendChild(aliases);
  const stopLabel=el("label",null,"忽略词条（每行一个）"); stopLabel.htmlFor="graph-stopwords"; box.appendChild(stopLabel);
  const stops=el("textarea"); stops.id="graph-stopwords"; stops.rows=3; stops.value=(settings.stopwords||[]).join("\n"); box.appendChild(stops);
  let adaptive=settings.adaptive!==false;
  chk(box,"抑制高频功能词","至少 8 篇文档，覆盖率达到 60% 的双字功能词可被抑制。",adaptive,value=>adaptive=value);
  const message=el("p","note"); message.setAttribute("role","status");
  const button=el("button",null,"保存图谱设置"); button.onclick=()=>{
    const mapping={};
    for(const line of aliases.value.split("\n").filter(x=>x.trim())){
      const pair=line.split("=").map(x=>x.trim());
      if(pair.length!==2 || pair.some(x=>x.length<2)){message.textContent="每行用等号分隔，词条至少两个字符。";return;}
      mapping[pair[0]]=pair[1];
    }
    S.conf.graph={aliases:mapping,stopwords:stops.value.split("\n").map(x=>x.trim()).filter(Boolean),adaptive};
    save(); GV.bridges=null; message.textContent="已保存到本机，登录时会同步并校验。";
  }; box.appendChild(button); box.appendChild(message);
  const sem=card(host,"语义召回（可选）","开启后，点击图谱中的语义召回会把文档文本发送给你选择的嵌入服务。默认关闭；不影响词条证据图谱。");
  const emb=S.conf.embeddings || {enabled:false,model_id:""};
  chk(sem,"启用嵌入服务","选择支持 /embeddings 的模型，调用可能产生服务商费用。",emb.enabled,value=>{S.conf.embeddings={...emb,enabled:value};save();});
  const select=el("select"); select.setAttribute("aria-label","嵌入模型");
  select.appendChild(new Option("选择嵌入模型",""));
  for(const m of S.conf.models||[]) select.appendChild(new Option(m.name,m.id));
  select.value=emb.model_id; select.onchange=()=>{S.conf.embeddings={...(S.conf.embeddings||emb),model_id:select.value};save();}; sem.appendChild(select);
}

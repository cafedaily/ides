/* Settings edits are explicit; idea edits remain autosaved. */
let settingsTab="models",settingsNotice="",modelDraft=null,modelBusy=false,modelTest=null,modelController=null;
let importEpoch=0;
let dv={enc:false,pass:"",inText:"",inPass:"",chk:null,encryptedInput:false,mode:"merge",includeModels:false,busy:"",out:null};
function card(host,title,hint){const c=el("section","settings-card");if(title)c.appendChild(el("h2",null,title));if(hint)c.appendChild(el("p","section-note",hint));host.appendChild(c);return c;}
function field(host,label,value,placeholder,onchange,type="text"){
  const row=el("div","setting-field"),name=el("label",null,label),input=el("input");input.id=uid("field-");name.htmlFor=input.id;
  input.type=type;input.value=value||"";input.placeholder=placeholder||"";input.oninput=()=>onchange(input.value);row.append(name,input);host.appendChild(row);return input;
}
function button(host,text,fn,primary=false){const b=el("button",primary?"main":"secondary",text);b.type="button";b.onclick=fn;host.appendChild(b);return b;}
function check(host,text,value,onchange){const label=el("label","check-row"),input=el("input");input.type="checkbox";input.checked=!!value;input.onchange=()=>onchange(input.checked);label.append(input,el("span",null,text));host.appendChild(label);return input;}
function inlineMessage(host,text,error=false){const note=el("p",error?"error-message":"success-message",text);note.setAttribute("role",error?"alert":"status");host.appendChild(note);return note;}
function stamp(){return new Date().toISOString().replace(/[:.]/g,"-").slice(0,19);}
function bytes(n){return n<1024?n+" B":n<1048576?(n/1024).toFixed(1)+" KB":(n/1048576).toFixed(2)+" MB";}
function downloadText(text,name){const url=URL.createObjectURL(new Blob([text],{type:"text/plain;charset=utf-8"}));const link=el("a");link.href=url;link.download=name;document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1500);}
function renderData(){
  const root=document.getElementById("v-data");root.textContent="";
  root.appendChild(el("p","eyebrow","你的空间，由你决定"));root.appendChild(el("h1","big d","空间设置"));
  root.appendChild(el("p","lede","连接自己的模型，整理自己的数据。所有设置保存在当前设备。"));
  const steps=el("div","progress-steps");for(const [n,label,done] of [[1,"创建空间",!!S.space],[2,"配置模型",!!selectedModel()],[3,"构建想法",!!S.ideas.length],[4,"导出备份",!!S.lastExport]]){
    const item=el("span",done?"complete":"",n+"  "+label);steps.appendChild(item);
  }root.appendChild(steps);
  const tabs=el("div","settings-tabs");tabs.setAttribute("role","tablist");tabs.setAttribute("aria-label","设置分类");
  for(const [id,label] of [["space","我的空间"],["models","模型配置"],["data","导入与导出"]]){
    const b=button(tabs,label,()=>{settingsTab=id;settingsNotice="";renderData();});b.id="settings-tab-"+id;b.setAttribute("role","tab");b.setAttribute("aria-selected",String(settingsTab===id));b.setAttribute("aria-controls","settings-panel");
  }root.appendChild(tabs);
  const panel=el("div","settings-panel");panel.id="settings-panel";panel.setAttribute("role","tabpanel");panel.setAttribute("aria-labelledby","settings-tab-"+settingsTab);root.appendChild(panel);
  if(settingsNotice)inlineMessage(panel,settingsNotice);
  if(settingsTab==="models")renderModels(panel);else if(settingsTab==="data")renderTransfer(panel);else renderSpaceSettings(panel);
}
function hasModelDraftChanges(){if(!modelDraft)return false;const old=S.conf.models.find(x=>x.id===modelDraft.id);return old?JSON.stringify(old)!==JSON.stringify(modelDraft):!!(modelDraft.name||modelDraft.base||modelDraft.model||modelDraft.key);}
function newModel(){modelDraft={id:uid("m-"),name:"",kind:"compat",base:"",model:"",key:""};modelTest=null;renderData();}
function renderModels(host){
  const models=S.conf.models||[];
  if(models.length){
    const list=card(host,"已连接的模型","只有你添加的模型会出现在这里。");
    for(const model of models){const row=el("div","model-row"),description=el("div");description.append(el("strong",null,model.name),el("p",null,model.model));
      if(S.conf.defaultModel===model.id || (!S.conf.defaultModel&&models[0]===model))description.appendChild(el("span","status-badge","默认模型"));
      row.appendChild(description);const actions=el("div","button-row");
      button(actions,"编辑",()=>{modelDraft=clone(model);modelTest=null;renderData();});
      if(S.conf.defaultModel!==model.id)button(actions,"设为默认",()=>{S.conf.defaultModel=model.id;save();_initAI();renderData();});
      button(actions,"移除",()=>{if(!confirm("移除模型配置「"+model.name+"」？已有想法会保留。"))return;S.conf.models=models.filter(x=>x.id!==model.id);if(S.conf.defaultModel===model.id)S.conf.defaultModel=S.conf.models[0]?.id||"";for(const action of Object.keys(S.conf.route||{}))if(S.conf.route[action]===model.id)delete S.conf.route[action];modelDraft=null;save();_initAI();renderData();});
      row.appendChild(actions);list.appendChild(row);
    }
    if(!modelDraft)button(list,"添加模型",newModel);
  }
  if(!models.length&&!modelDraft)modelDraft={id:uid("m-"),name:"",kind:"compat",base:"",model:"",key:""};
  if(modelDraft)renderModelForm(host);
  if(models.length){
    const details=el("details","settings-card");details.appendChild(el("summary",null,"高级：不同动作使用不同模型"));
    for(const [action,label] of [["name","起名字"],["ask","追问与成形"],["angle","换个角度"],["collide","碰一下"],["rewrite","重写"]]){
      const wrap=el("div","setting-field"),name=el("label",null,label),select=el("select");select.id="route-"+action;name.htmlFor=select.id;
      select.appendChild(new Option("跟随默认模型",""));models.forEach(m=>select.appendChild(new Option(m.name,m.id)));select.value=S.conf.route?.[action]||"";
      select.onchange=()=>{S.conf.route=S.conf.route||{};if(select.value)S.conf.route[action]=select.value;else delete S.conf.route[action];save();showToast("模型分工已保存到本机。");};wrap.append(name,select);details.appendChild(wrap);
    }host.appendChild(details);
    const actions=el("div","next-action");actions.appendChild(el("p",null,"配置就绪，记下第一个值得继续想的念头。"));button(actions,"开始构建想法",()=>go("new"),true);host.appendChild(actions);
  }
}
function renderModelForm(host){
  const draft=modelDraft,exists=S.conf.models.some(x=>x.id===draft.id),box=card(host,exists?"编辑模型":"连接你自己的模型","支持 OpenAI 兼容接口，也可以连接允许浏览器访问的本地模型服务。");
  const form=el("form","model-form");box.appendChild(form);
  const change=(key,value)=>{draft[key]=value;modelTest=null;form.querySelector(".model-feedback").textContent="有未保存的修改";};
  field(form,"配置名称",draft.name,"例如：写作模型",v=>change("name",v)).required=true;
  field(form,"服务地址",draft.base,"https://api.example.com/v1",v=>change("base",v)).required=true;
  form.appendChild(el("p","field-help","填写接口基础地址。使用浏览器直连时，服务需要允许当前网站跨域访问。"));
  field(form,"模型 ID",draft.model,"服务商提供的完整模型名称",v=>change("model",v)).required=true;
  const secret=field(form,"API Key",draft.key,"本地服务不需要时可留空",v=>change("key",v),"password");secret.autocomplete="off";secret.spellcheck=false;
  check(form,"显示 API Key",false,visible=>secret.type=visible?"text":"password");
  form.appendChild(el("p","field-help","密钥只保存在当前浏览器；导出未加密文件时不会包含密钥。"));
  const feedback=el("p","model-feedback");feedback.setAttribute("role","status");feedback.textContent=modelTest?.message||"填写后可以测试连接，也可以直接保存。";if(modelTest?.error)feedback.classList.add("error-message");form.appendChild(feedback);
  const row=el("div","button-row");
  const test=button(row,modelBusy?"测试中…":"测试连接",async()=>{
    try{validateModel(draft);}catch(e){feedback.textContent=e.message;feedback.classList.add("error-message");return;}
    const sent=clone(draft);modelBusy=true;test.disabled=true;saveButton.disabled=true;feedback.classList.remove("error-message");feedback.textContent="正在发送简短测试请求…";modelController=new AbortController();
    try{await testModel(sent,modelController.signal);modelTest={message:JSON.stringify(sent)===JSON.stringify(draft)?"连接成功。可以保存并开始使用。":"测试成功，但配置已修改，请重新测试。"};}
    catch(e){modelTest={message:e.message,error:true};}
    finally{modelBusy=false;modelController=null;test.disabled=false;saveButton.disabled=false;feedback.textContent=modelTest.message;feedback.classList.toggle("error-message",!!modelTest.error);}
  });test.disabled=modelBusy;
  const saveButton=el("button","main",exists?"保存修改":"保存模型");saveButton.type="submit";saveButton.disabled=modelBusy;row.appendChild(saveButton);
  button(row,"取消",()=>{if(hasModelDraftChanges()&&!confirm("放弃尚未保存的模型修改？"))return;modelController?.abort();modelDraft=null;modelTest=null;renderData();});form.appendChild(row);
  form.onsubmit=async event=>{event.preventDefault();try{
    draft.base=draft.base.trim().replace(/\/chat\/completions\/?$/,"").replace(/\/$/,"");draft.name=draft.name.trim();draft.model=draft.model.trim();draft.key=draft.key.trim();validateModel(draft);
    S.conf.models=S.conf.models.filter(x=>x.id!==draft.id).concat([clone(draft)]);if(!S.conf.defaultModel)S.conf.defaultModel=draft.id;
    save();await dbWrite();if(DB.pending)throw new Error(DB.why);modelDraft=null;modelTest=null;_initAI();settingsNotice="模型已保存到当前设备。";renderData();
  }catch(e){feedback.textContent=e.message;feedback.classList.add("error-message");}};
}
function renderSpaceSettings(host){
  const box=card(host,"空间信息","每个空间的想法和模型配置彼此独立。");let name=S.space.name;
  field(box,"空间名称",name,"给这个空间取个名字",value=>name=value);
  button(box,"保存名称",()=>{if(!name.trim()||name.trim().length>60){showToast("名称为 1–60 个字符。",true);return;}S.space.name=name.trim();save();showToast("空间名称已保存。");},true);
  const summary=el("div","space-stats");for(const [count,label] of [[S.ideas.length,"想法"],[S.sparks.length,"念头"],[S.cold.length,"归档"]]){const item=el("div");item.append(el("strong",null,String(count)),el("span",null,label));summary.appendChild(item);}box.appendChild(summary);
  const other=card(host,"切换空间","数据只在此设备上；换设备时可通过导出、导入继续使用。");
  for(const space of spaceIndex){const row=el("div","model-row");row.appendChild(el("span",null,space.name));const b=button(row,space.id===SPACE?"当前空间":"切换",async()=>{try{await switchSpace(space.id);}catch(e){showToast(e.message,true);}});b.disabled=space.id===SPACE;other.appendChild(row);}
  let newName="";field(other,"新空间名称","","例如：下一个项目",v=>newName=v);
  button(other,"创建另一个空间",async()=>{try{if(hasModelDraftChanges()&&!confirm("模型配置尚未保存。放弃这些修改并创建空间？"))return;for(const controller of MODEL_REQUESTS)controller.abort();await createSpace(newName);workspaceEpoch++;modelDraft=null;_initAI();settingsTab="models";renderData();paintSession();}catch(e){showToast(e.message,true);}});
  const graph=card(host,"词条归并","图谱在当前设备计算，不需要发送想法内容。");
  let aliasesText=Object.entries(S.conf.graph?.aliases||{}).map(([a,b])=>a+"="+b).join("\n");
  const label=el("label",null,"同义词（每行：别名=标准词）"),area=el("textarea");area.id="aliases";label.htmlFor=area.id;area.rows=4;area.value=aliasesText;area.oninput=()=>aliasesText=area.value;graph.append(label,area);
  let stops=(S.conf.graph?.stopwords||[]).join("、");field(graph,"忽略词条",stops,"用逗号或顿号分隔",v=>stops=v);
  button(graph,"保存词条设置",()=>{try{const aliases={};for(const line of aliasesText.split("\n").filter(x=>x.trim())){const [a,b,...extra]=line.split("=").map(x=>x.trim());if(!a||!b||extra.length||a.length<2||b.length<2)throw new Error("同义词每行用等号分隔，词条至少两个字符。");aliases[a]=b;}localAliases({aliases});S.conf.graph={...(S.conf.graph||{}),aliases,stopwords:stops.split(/[,，、\n]/).map(x=>x.trim()).filter(Boolean)};GV.bridges=null;save();showToast("词条设置已保存。");}catch(e){showToast(e.message,true);}});
}
function renderTransfer(host){
  const backup=card(host,"导出空间","下载一份完整备份，包含想法、念头、归档与模型配置。");
  backup.appendChild(el("p","field-help",S.lastExport?"上次导出："+new Date(S.lastExport).toLocaleString():"还没有导出备份。建议在换设备或清理浏览器前保存一份。"));
  check(backup,"使用口令加密（同时包含模型密钥）",dv.enc,value=>{dv.enc=value;dv.out=null;renderData();});
  let exportButton;
  if(dv.enc)field(backup,"备份口令",dv.pass,"至少 8 个字符",v=>{dv.pass=v;exportButton.disabled=v.length<8;},"password");
  else backup.appendChild(el("p","field-help","普通备份不含模型密钥，导入后可重新填写。"));
  exportButton=button(backup,dv.busy==="export"?"正在生成备份…":"导出备份",doExport,true);exportButton.disabled=dv.busy==="export"||(dv.enc&&dv.pass.length<8);
  if(dv.out)inlineMessage(backup,dv.out.message,dv.out.error);
  const importer=card(host,"导入数据","先校验文件并预览内容，再选择合并或替换。");
  const label=el("label","file-picker","选择备份文件"),file=el("input");file.type="file";file.accept=".jsonl,.txt,.json";file.id="import-file";label.htmlFor=file.id;importer.append(label,file);
  file.onchange=async()=>{const epoch=++importEpoch;const selected=file.files?.[0];if(!selected)return;if(selected.size>40*1024*1024){inlineMessage(importer,"文件不能超过 40 MB。",true);return;}const text=await selected.text();if(epoch!==importEpoch)return;dv.inText=text;dv.inPass="";dv.encryptedInput=false;await doCheck();};
  if(dv.chk?.needPass||dv.encryptedInput){field(importer,"解密口令",dv.inPass,"输入导出时设置的口令",v=>dv.inPass=v,"password");button(importer,dv.busy==="check"?"校验中…":"解密并校验",doCheck,true).disabled=dv.busy==="check";}
  if(dv.chk&&!dv.chk.ok&&!dv.chk.needPass)inlineMessage(importer,(dv.chk.errors||[]).map(x=>x.msg).join("；"),true);
  if(dv.chk?.ok){
    inlineMessage(importer,"校验通过："+dv.chk.counts.idea+" 个想法、"+dv.chk.counts.spark+" 条念头、"+dv.chk.counts.cold+" 条归档。");
    const choice=el("div","import-choices");
    for(const [mode,title,description] of [["merge","合并到当前空间","保留当前空间独有的记录，相同 ID 保留较新的内容。"],["replace","替换当前内容","替换想法、念头和归档；导入前会先下载当前空间的安全副本。"]]){
      const item=el("label","import-choice"),radio=el("input");radio.type="radio";radio.name="import-mode";radio.value=mode;radio.checked=dv.mode===mode;radio.onchange=()=>dv.mode=mode;const text=el("div");text.append(el("strong",null,title),el("p",null,description));item.append(radio,text);choice.appendChild(item);
    }importer.appendChild(choice);
    check(importer,"同时导入模型配置",dv.includeModels,value=>dv.includeModels=value);
    button(importer,"确认导入",applyImport,true);
  }
  const local=card(host,"保存位置",DB.ok?"此设备的浏览器数据库（IndexedDB）":"此设备的浏览器简易存储（localStorage）");
  local.appendChild(el("p","field-help","关闭页面后内容仍会保留。清除网站数据会删除本机空间；备份文件可用于恢复。"));
}
async function doExport(){
  dv.busy="export";dv.out=null;renderData();
  try{await dbWrite();const state=payloadState(S);state.conf.workspace=clone(S.space);const result=await YD.exportJSONL(state,{pass:dv.enc?dv.pass:null});
    downloadText(result.text,"想法空间-"+stamp()+(dv.enc?"-加密":"")+".jsonl");S.lastExport=Date.now();save();dv.out={message:"备份已下载。"};
  }catch(e){dv.out={message:"导出失败："+e.message,error:true};}finally{dv.busy="";renderData();}
}
async function doCheck(){
  const epoch=++importEpoch;dv.busy="check";
  let result;try{result=await YD.parseJSONL(dv.inText,{pass:dv.inPass||null});}catch(e){result={ok:false,errors:[{msg:e.message}]};}
  if(epoch!==importEpoch)return;
  dv.chk=result;dv.encryptedInput=dv.encryptedInput||!!result.needPass;dv.busy="";renderData();
}
async function applyImport(){
  try{
    if(dv.mode==="replace"){const backup=await YD.exportJSONL(payloadState(S),{});downloadText(backup.text,"替换前备份-"+stamp()+".jsonl");}
    const records=dv.includeModels?dv.chk.recs:dv.chk.recs.filter(r=>r.t!=="conf");
    const out=YD.apply(payloadState(S),records,dv.mode);
    if(dv.includeModels && out.conf){out.conf.models=(out.conf.models||[]).filter(model=>model.base&&model.model).map(model=>({...model,key:model.key||""}));if(!out.conf.models.some(m=>m.id===out.conf.defaultModel))out.conf.defaultModel=out.conf.models[0]?.id||"";out.conf.route=out.conf.route||{};for(const key of Object.keys(out.conf.route))if(!out.conf.models.some(m=>m.id===out.conf.route[key]))delete out.conf.route[key];}
    S.ideas=out.ideas;S.sparks=out.sparks||[];S.cold=out.cold;if(dv.includeModels&&out.conf)S.conf=Object.assign(defaultConf(),out.conf);
    save();await dbWrite();if(DB.pending)throw new Error(DB.why);_initAI();GV.bridges=null;
    dv.chk=null;dv.inText="";dv.inPass="";settingsNotice="数据已导入当前空间。";renderData();
  }catch(e){showToast("导入未完成："+e.message,true);}
}

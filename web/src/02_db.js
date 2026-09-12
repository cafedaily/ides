/* Each personal space is an independent, device-local database. */
const DB={name:"",h:null,ok:false,why:"",rev:0,pending:null,writing:null,conflict:null,lastDigest:null};
const SPACE_INDEX="yang.spaces.v3", ACTIVE_SPACE="yang.active.v3";
let spaceIndex=[];
try{spaceIndex=JSON.parse(localStorage.getItem(SPACE_INDEX)||"[]");if(!Array.isArray(spaceIndex))spaceIndex=[];}catch(e){}
function clone(value){return JSON.parse(JSON.stringify(value));}
function safeState(value){const out=clone(value);delete out.syncBase;delete out.revision;return out;}
function contentDigest(state){return JSON.stringify({space:state.space,ideas:state.ideas,sparks:state.sparks,cold:state.cold,conf:state.conf,lastExport:state.lastExport});}
function draftKey(){return "yang.draft."+SPACE;}
function save(){
  if(!S.space || !SPACE)return;
  if(!DB.pending && !DB.writing && !DB.conflict && contentDigest(S)===DB.lastDigest)return;
  DB.pending=safeState(S);
  try{sessionStorage.setItem(draftKey(),JSON.stringify({base:DB.rev,state:DB.pending}));}catch(e){}
  if(typeof paintSession==="function")paintSession();
  void dbWrite();
}
async function dbWrite(){
  if(DB.writing)return DB.writing;
  if(!DB.pending || DB.conflict)return;
  DB.writing=(async()=>{
    while(DB.pending && !DB.conflict){
      const snapshot=DB.pending;DB.pending=null;
      try{
        const revision=await persistSnapshot(snapshot);
        DB.rev=revision;DB.lastDigest=contentDigest(snapshot);DB.why="";
        if(!DB.pending)try{sessionStorage.removeItem(draftKey());}catch(e){}
        const currentIndex=JSON.parse(localStorage.getItem(SPACE_INDEX)||"[]");
        for(const item of currentIndex)if(!spaceIndex.some(x=>x.id===item.id))spaceIndex.push(item);
        const item=spaceIndex.find(x=>x.id===SPACE);
        if(item){item.name=snapshot.space.name;item.updated=Date.now();}
        localStorage.setItem(SPACE_INDEX,JSON.stringify(spaceIndex));
      }catch(error){DB.pending=DB.pending||snapshot;DB.why=error.message;break;}
    }
  })();
  try{await DB.writing;}finally{DB.writing=null;if(typeof paintSession==="function")paintSession();}
}
function persistSnapshot(state){
  const next={revision:DB.rev+1,state};
  if(!DB.ok){
    return new Promise((resolve,reject)=>{
      try{
        const remote=JSON.parse(localStorage.getItem(DB.name)||"null");
        if((remote?.revision||0)!==DB.rev){DB.conflict=remote;throw new Error("另一窗口更新了这个空间，请先处理保存冲突。");}
        localStorage.setItem(DB.name,JSON.stringify(next));resolve(next.revision);
      }catch(e){reject(e);}
    });
  }
  return new Promise((resolve,reject)=>{
    const tx=DB.h.transaction("kv","readwrite"),store=tx.objectStore("kv"),request=store.get("snapshot");
    let failure;
    request.onsuccess=()=>{
      const remote=request.result;
      if((remote?.revision||0)!==DB.rev){DB.conflict=remote;failure=new Error("另一窗口更新了这个空间，请先处理保存冲突。");tx.abort();return;}
      store.put(next,"snapshot");
    };
    tx.oncomplete=()=>resolve(next.revision);
    tx.onerror=tx.onabort=()=>reject(failure||new Error("本地保存失败，请导出备份后重试。"));
  });
}
async function openLocalSpace(id){
  if(DB.writing)await DB.writing;
  if(DB.pending || DB.conflict)throw new Error("当前修改尚未保存，请先重试保存或处理冲突。");
  if(DB.h)DB.h.close();
  SPACE=id;DB.name="yang.space.v3."+id;DB.h=null;DB.ok=false;DB.rev=0;DB.conflict=null;DB.why="";
  let stored=null;
  try{
    DB.h=await new Promise((resolve,reject)=>{
      const rq=indexedDB.open(DB.name,1);
      rq.onupgradeneeded=()=>rq.result.createObjectStore("kv");
      rq.onsuccess=()=>resolve(rq.result);rq.onerror=()=>reject(rq.error);
      rq.onblocked=()=>reject(new Error("请关闭其他旧版窗口后重试。"));
    });DB.ok=true;
    stored=await new Promise((resolve,reject)=>{const r=DB.h.transaction("kv").objectStore("kv").get("snapshot");r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});
    // A prior storage fallback is migrated once, retaining its revision and contents.
    if(!stored){const fallback=JSON.parse(localStorage.getItem(DB.name)||"null");if(fallback){stored={revision:0,state:fallback.state};}}
  }catch(e){DB.ok=false;DB.why="浏览器数据库不可用，使用本机简易存储。";stored=JSON.parse(localStorage.getItem(DB.name)||"null");}
  DB.rev=stored?.revision||0;
  S=stored?.state || emptyState();DB.lastDigest=stored?contentDigest(S):null;
  try{
    const draft=JSON.parse(sessionStorage.getItem(draftKey())||"null");
    if(draft){S=draft.state;DB.pending=clone(S);if(draft.base!==DB.rev && stored){DB.conflict=stored;DB.why="有未保存草稿与另一窗口的修改，请选择保留版本。";}}
  }catch(e){}
  localStorage.setItem(ACTIVE_SPACE,id);
  S.conf=Object.assign(defaultConf(),S.conf||{});S.conf.models=S.conf.models||[];
  return S;
}
async function resolveLocalConflict(choice){
  if(!DB.conflict)return;
  if(choice==="remote")S=clone(DB.conflict.state);
  DB.rev=DB.conflict.revision;DB.conflict=null;DB.why="";
  save();await dbWrite();_initAI();render();
}
async function createSpace(name){
  name=name.trim();if(!name || name.length>60)throw new Error("空间名称为 1–60 个字符。");
  const id=uid("space-");await openLocalSpace(id);
  S=emptyState();S.space={id,name,created:Date.now()};
  spaceIndex.push({id,name,updated:Date.now()});save();await dbWrite();
  if(DB.pending)throw new Error(DB.why||"空间尚未保存。");
  return id;
}

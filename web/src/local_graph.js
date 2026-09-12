/* Device-only lexical graph. Source sentences never leave this browser. */
let LOCAL_GRAPH_CACHE={signature:null,result:null};
function localAliases(settings={}){
  const mapping=Object.assign(Object.create(null),{llm:"大模型",llms:"大模型","大语言模型":"大模型"});
  for(const [key,value] of Object.entries(settings.aliases||{})){if(typeof value!=="string"||key.length<2||value.length<2)throw new Error("同义词必须至少包含两个字符。");mapping[key.toLowerCase()]=value.toLowerCase();}
  for(const source of Object.keys(mapping)){const seen=new Set([source]);let target=mapping[source];while(mapping[target]&&mapping[target]!==target){if(seen.has(target))throw new Error("同义词存在循环，请改成统一的标准词。");seen.add(target);target=mapping[target];}mapping[source]=target;}
  return mapping;
}
function localDocuments(){
  const docs=S.ideas.map(i=>({id:i.id,title:i.title,kind:"idea",pieces:[{dim:"title",text:i.title},{dim:"seed",text:i.seed||""},{dim:"now",text:i.now||""},...(i.grew||[]).map(g=>({dim:g.kind,text:g.q+"\n"+g.a}))]}));
  for(const x of S.cold)docs.push({id:x.id,title:x.title,kind:"cold",pieces:[{dim:"title",text:x.title},{dim:"why",text:x.why}]});
  for(const x of S.sparks)docs.push({id:x.id,title:x.text.slice(0,24),kind:"spark",pieces:[{dim:"spark",text:x.text}]});
  return docs;
}
function localGraph(){
  const documents=localDocuments(),settings=S.conf.graph||{},signature=JSON.stringify([documents,settings]);
  if(LOCAL_GRAPH_CACHE.signature===signature)return LOCAL_GRAPH_CACHE.result;
  const aliases=localAliases(settings),escaped=Object.keys(aliases).sort((a,b)=>b.length-a.length).map(x=>x.replace(/[.*+?^${}()|[\]\\]/g,"\\$&"));
  const pattern=new RegExp(escaped.map(x=>/^[a-z]+$/.test(x)?"\\b"+x+"\\b":x).join("|"),"gi");
  const normalize=text=>String(text).normalize("NFKC").toLowerCase().replace(pattern,match=>aliases[match.toLowerCase()]).replace(/每一(?=[步次天周年月个篇])/g,"每");
  const stops=new Set(["一个","这个","那个","我们","他们","可以","不是","没有","如果","因为","所以","什么","怎么","就是",...(settings.stopwords||[])]);
  const raw=new Map(),frequencies=new Map();
  for(const doc of documents){const terms=new Map();for(const piece of doc.pieces){const text=normalize(piece.text),tokens=new Set(text.match(/[a-z][a-z0-9_-]{1,}/g)||[]);
      for(const run of text.match(/[\u3400-\u9fff]+/g)||[])for(let n=2;n<=Math.min(4,run.length);n++)for(let i=0;i<=run.length-n;i++){const term=run.slice(i,i+n);if(stops.has(term)||/^[的了和是在有这那我你他她它们个]|[的了和是在这那个]$/.test(term))continue;tokens.add(term);}
      for(const term of tokens){if(stops.has(term))continue;const value=terms.get(term)||{term,tf:0,dims:[],evidence:{dim:piece.dim,text:piece.text.split(/[。！？\n]/).find(sentence=>normalize(sentence).includes(term))||piece.text}};value.tf+=piece.dim==="title"?2:1;if(!value.dims.includes(piece.dim))value.dims.push(piece.dim);terms.set(term,value);}
    }raw.set(doc.id,terms);for(const term of terms.keys())frequencies.set(term,(frequencies.get(term)||0)+1);}
  const terms=Object.create(null),inverted=new Map();
  for(const doc of documents){const all=[...raw.get(doc.id).values()].map(item=>({...item,w:item.tf*Math.log(1+documents.length/(frequencies.get(item.term)||1))}));
    all.sort((a,b)=>b.w-a.w||b.term.length-a.term.length||a.term.localeCompare(b.term));const chosen=[];
    for(const item of all){if(chosen.some(x=>x.term.includes(item.term)&&frequencies.get(x.term)===frequencies.get(item.term)))continue;chosen.push(item);if(chosen.length===40)break;}
    terms[doc.id]=chosen;for(const item of chosen){const list=inverted.get(item.term)||[];list.push({doc,item});inverted.set(item.term,list);}}
  const bridges=[];
  for(const [term,members] of inverted){if(members.length<2)continue;for(let i=0;i<members.length;i++)for(let j=i+1;j<members.length;j++){
    const a=members[i],b=members[j],bonus=a.item.dims.includes("why")||b.item.dims.includes("why")?1.8:a.item.dims.join()!=b.item.dims.join()?1.4:1;
    bridges.push({term,a:a.doc.id,b:b.doc.id,a_title:a.doc.title,b_title:b.doc.title,a_dims:a.item.dims,b_dims:b.item.dims,a_say:a.item.evidence,b_say:b.item.evidence,bonus,score:a.item.w*b.item.w*bonus});
  }}bridges.sort((a,b)=>b.score-a.score||b.term.length-a.term.length||a.term.localeCompare(b.term));
  const chosen=[];for(const bridge of bridges){if(chosen.some(x=>x.a===bridge.a&&x.b===bridge.b&&(x.term.includes(bridge.term)||bridge.term.includes(x.term))))continue;chosen.push(bridge);}
  const result={documents,terms,bridges:chosen};LOCAL_GRAPH_CACHE={signature,result};return result;
}
function localPath(a,b){
  const graph=localGraph(),byId=new Map(graph.documents.map(x=>[x.id,x])),neighbors=new Map();
  for(const bridge of graph.bridges){for(const [left,right] of [[bridge.a,bridge.b],[bridge.b,bridge.a]]){const list=neighbors.get(left)||[];list.push({id:right,term:bridge.term});neighbors.set(left,list);}}
  if(!byId.has(a)||!byId.has(b))return {found:false,why:"请先选择当前空间里的两个想法。"};
  const queue=[a],parent=new Map([[a,null]]);while(queue.length){const id=queue.shift();if(id===b)break;for(const next of neighbors.get(id)||[])if(!parent.has(next.id)){parent.set(next.id,{id,term:next.term});queue.push(next.id);}}
  if(!parent.has(b))return {found:false,why:"目前没有由共同词条连接的路径。可以在空间设置中补充同义词。"};
  const steps=[];let id=b;while(id!==a){steps.unshift({type:"idea",ref:id,label:byId.get(id).title});const previous=parent.get(id);steps.unshift({type:"term",ref:previous.term,label:previous.term});id=previous.id;}steps.unshift({type:"idea",ref:a,label:byId.get(a).title});return {found:true,hops:steps.length-1,steps};
}

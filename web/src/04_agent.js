
/* ================== 智能体 ================== */
let AI = null;                 // 拿不到就是 null，全站照常跑
let liveAbort = null;

async function _initAI(){
  try{ if(window.claude && typeof claude.use === "function"){
    const s = await claude.use("sample");
    if(s){ AI = s; render(); return; } } }catch(e){}
  if(API.on || await API.probe()){
    AI = async function(input, opts){
      opts = opts || {};
      const sys = typeof input === "string" ? null : (input.system || null);
      const user = typeof input === "string" ? input : (input.user || input.prompt || String(input));
      const msgs = [];
      if(sys) msgs.push({role:"system", content:sys});
      msgs.push({role:"user", content:user});
      const body = { messages:msgs };
      if(opts.json) body.json = true;
      if(opts.action) body.action = opts.action;
      if(opts.onText && !opts.json) body.stream = true;
      const r = body.stream ? await API._postStream("/api/chat", body, { signal:opts.signal, onText:opts.onText })
                            : await API._post("/api/chat", body, { signal:opts.signal });
      if(!r.ok) throw new Error(r.error || "模型调用失败");
      const text = (r.text || "").trim();
      if(opts.json){ try{ return JSON.parse(text); }catch(e){ return null; } }
      return { text };
    };
    AI.json = async function(input, opts){
      return await AI(input, Object.assign({}, opts, { json:true }));
    };
    render();
  }
}

function stopLive(){ if(liveAbort){ try{ liveAbort.abort(); }catch(e){} liveAbort=null; } }
function tone(){
  const c=S.conf||{};
  return (c.len==="two" ? "最多写两句。" : "只写一句话。")
    + ({ soft:"顺着他的思路往下问，别拆台。",
         normal:"挑他含糊带过的那一处问。",
         hard:"专找最站不住的地方下手，不用替他留面子。" }[c.sharp||"normal"]) + "\n";
}
const NOSLOP = "中文，直接对他说。必须贴着这个想法本身，把里面的具体东西说出来。"
  + "不要通用套话，不要「你可以考虑」这类废话，不要引号、编号、解释、开场白。";

function actionFromPrompt(input){
  const s = typeof input === "string" ? input : ((input && (input.user || input.prompt || input.system)) || "");
  if(s.indexOf("给下面这个想法起个名字")>=0) return "name";
  if(s.indexOf("按记录重写")>=0 || s.indexOf("把这些揉成一段")>=0) return "rewrite";
  if(s.indexOf("碰一下")>=0 || s.indexOf("撞在一起")>=0 || s.indexOf("硬塞进这个想法")>=0) return "collide";
  if(s.indexOf("换个角度")>=0 || s.indexOf("换角度")>=0) return "angle";
  if(s.indexOf("追问")>=0 || s.indexOf("逼他把")>=0) return "ask";
  return null;
}
async function say(input, o){
  const epoch=workspaceEpoch;
  o = o || {};
  if(!AI) return null;
  const action = o.action || actionFromPrompt(input);
  if(o.json){
    const value=await AI.json(input,{modelTier:o.tier||"default",action,signal:o.signal,cache:o.cache!==false});
    if(epoch!==workspaceEpoch) throw new Error("空间已切换");
    return value;
  }
  const r = await AI(input, { modelTier:o.tier||"quick", action:action, signal:o.signal, onText:o.onText, cache:false });
  if(epoch!==workspaceEpoch) throw new Error("空间已切换");
  return String(r && r.text || "").trim().replace(/^[「『"']+|[」』"']+$/g,"").trim();
}
function ideaCtx(it){
  let s = "名字：「"+it.title+"」\n最初那句：" + (it.seed || "（没记）");
  const n=(it.now||"").trim();
  if(n) s += "\n他现在写的是：\n" + n.slice(0,900);
  if(it.grew.length && S.conf.seeGrew !== false){
    s += "\n\n已经问过的（别重复，也别只是换个说法）：";
    it.grew.slice(-8).forEach(g=>{ s += "\n· "+KIND[g.kind]+"："+g.q+"\n  他答："+String(g.a).slice(0,300); });
  }
  return s;
}
const KIND = { ask:"追问", angle:"换个角度", collide:"碰一下", note:"随手记" };
const TASK = {
  ask:"提一个追问，逼他把这个想法说得更具体。挑他还没想清楚、或者含糊带过的那一处下手。",
  angle:"给他一个换角度的指令，把这个想法掰弯：换一种载体、换一群人、换一个极端条件、或者假装它已经失败了。要具体到他能立刻动笔。"
};
const ASK = ["谁会第一个用它？说一个具体的人，别说「年轻人」。","那个人现在是怎么凑合的？",
  "它解决的到底是麻烦，还是无聊？","如果这么明显，为什么到现在还没人做？","你放不下它的，到底是哪一点？",
  "去掉最花哨的那部分，还剩什么？","如果只能留十分之一，留哪个十分之一？","什么样的人会讨厌它？",
  "它最像已经存在的哪个东西？差在哪？","第一个用的人，会怎么跟朋友形容它？","一个人用有意思吗？还是得一群人？",
  "它在什么时刻被想起——早上、深夜、还是排队的时候？","如果它不赚钱，你还想做吗？",
  "它让人多一件事做，还是少一件事做？","最坏的情况下，它会变成什么样的东西？","它有没有一个特别小、特别土的版本？",
  "十年前做得出来吗？为什么现在可以了？","如果它成了，世界上会多出什么、少掉什么？",
  "你想拿它给谁看？为什么是那个人？","它的名字叫什么？名字里藏着什么？","它最怕遇到哪一句话？"];
const ANGLE = ["把它变成一个能拿在手里的东西。什么材质，多重？","把它变成一场活动。谁来，做什么，几点散？",
  "假装它已经上线两年了。写一条最扎心的差评。","假装它死了。写一句讣告，说明死因。","让它贵到离谱。谁会买？",
  "让它彻底免费而且很土。还剩什么价值？","换一个完全不搭的行业来做它——菜市场、殡葬、幼儿园。",
  "只给你一个周末和一部手机。你做什么？","把它缩到一张纸上。这张纸上写什么？",
  "让一个八十岁的人来用。他在哪一步卡住？","把它做成一个游戏。规则是什么，怎么赢？",
  "把它反过来做。反过来是什么意思？","它是一首歌的话，是什么调子？","如果只能在一个地方存在，是哪儿？"];
const STUFF = ["菜市场","夜班","复印店","老照片","下雨天","闹钟","公园长椅","超市小票","理发店","搬家",
  "体检报告","二手书","天台","外卖箱","旧手机","值班室","修车摊","婚礼","门牌号","暖气片","走失的猫",
  "快递柜","地铁末班车","电梯","社区公告栏","旧钥匙","晾衣绳","路边摊","水电费单","迷路","集邮册",
  "幼儿园门口","加油站","招牌","旧同学录","雨伞架","寄存柜","医院走廊","过期优惠券","一副没配好的眼镜"];

function fallbackQ(kind,it,used){
  if(kind==="ask")   return { q:pick(ASK,used) };
  if(kind==="angle") return { q:pick(ANGLE,used) };
  const others=(S.conf.seeOthers!==false) ? S.ideas.filter(x=>x.id!==it.id && (x.now||x.seed)) : [];
  if(others.length && Math.random()<0.4){
    const o=others[Math.floor(Math.random()*others.length)];
    return { q:"把你另一个想法「"+o.title+"」和这个放一起。它们能凑成第三个东西吗？", with:o.id };
  }
  return { q:"把「"+pick(STUFF,[])+"」硬塞进这个想法里。不用合理，看看会撞出什么。" };
}

function cleanTitle(t,fb){
  let x=String(t||"").trim().replace(/^[「『"\u2018\u201c]+|[」』"\u2019\u201d]+$/g,"").trim();
  x=x.split(/[。？！\n]/)[0].trim();          // 名字不是一句话，更不是一个问句
  x=x.replace(/[，,、：:；;]\s*$/,"");
  if(!x || x.length>24) return fb;
  return x;
}

/* 念头 → 想法 */
async function agShape(text){
  if(!AI) return { title:text.trim().slice(0,14), seed:text.trim(), first:pick(ASK,[]) };
  try{
    const r = await say(
      "下面是一个人随手记下的念头，还没成形：\n\n" + text.trim() +
      "\n\n把它变成一个可以开始养的想法。只回 JSON："+
      '{"title":"…","seed":"…","first":"…"}\n'+
      "title：给它起个名字，不超过 14 个字，用他自己的词。不要加「平台」「系统」「助手」这类壳子。\n"+
      "seed：把这句念头理成一句话，保留他原来的说法，别拔高，别替他扩写。\n"+
      "first：一个追问，逼他把这个念头说具体。要贴着它本身，不要通用问题。",
      { json:true, tier:"quick", action:"ask" });
    if(r && typeof r.title==="string" && r.title.trim())
      return { title:cleanTitle(r.title, text.trim().slice(0,14)),
               seed:(r.seed||text).trim().slice(0,600),
               first:(r.first||pick(ASK,[])).trim().slice(0,300) };
  }catch(e){}
  return { title:text.trim().slice(0,14), seed:text.trim(), first:pick(ASK,[]) };
}
/* 起名 */
async function agName(it){
  const r = await say("给下面这个想法起个名字。\n\n"+ideaCtx(it)+
    "\n\n不超过 14 个字，用他自己的词，别加「平台」「系统」「助手」这类壳子。只回名字本身。",
    { tier:"quick", action:"name" });
  return r ? cleanTitle(r, null) : null;
}
/* 分叉方向 */
async function agFork(it){
  if(!AI) return [{title:"把它做小十倍",why:"只留一个人一个下午能做完的那部分。"},
                  {title:"换一群人用",why:"同样的机制，换一个完全不同的人群。"},
                  {title:"最土的那一版",why:"不用电、不用网，用纸和嘴也能跑的版本。"}];
  try{
    const r = await say("下面是一个人正在养的想法。\n\n"+ideaCtx(it)+
      "\n\n给他三个分叉方向：从这个想法里长出来、但会走向别处的三个东西。只回 JSON："+
      '{"dirs":[{"title":"…","why":"…"},…]}\n'+
      "title 不超过 14 个字，是分出去那个想法的名字。why 一句话，说清它和原来那个的分岔点在哪。"+
      "三个要真的不一样，不要三个同义词。用他答里出现过的具体东西。", { json:true });
    if(r && Array.isArray(r.dirs) && r.dirs.length)
      return r.dirs.slice(0,3).map(d=>({ title:cleanTitle(d.title,"")||String(d.title||"").slice(0,24),
                                         why:String(d.why||"").slice(0,200) })).filter(d=>d.title);
  }catch(e){}
  return null;
}
/* 凉了的里的规律 */
async function agPattern(){
  const list = S.cold.slice(0,12).map(c=>"·「"+c.title+"」——"+String(c.why).slice(0,300)).join("\n");
  return await say("下面是一个人放弃掉的想法，和他当时写下的放弃理由：\n\n"+list+
    "\n\n他放弃的理由里有没有反复出现的同一件事？有就直说是什么，用他自己的话举出证据；"+
    "没有就直说没有，别硬编。三到五句，中文，平静，别安慰他，也别说教。");
}
/* 今天动哪一个 */
async function agPick(){
  const live = S.ideas.slice(0,20);
  if(!live.length) return null;
  if(!AI){ const o=live.slice().sort((a,b)=>lastAt(a)-lastAt(b))[0];
    return { id:o.id, why:"它停得最久，"+ago(lastAt(o))+"没动过。" }; }
  try{
    const list = live.map(i=>"id="+i.id+" 「"+i.title+"」 上次动是"+ago(lastAt(i))+
      "，长了 "+i.grew.length+" 回。现在写的："+String(i.now||i.seed||"").slice(0,120)).join("\n");
    const r = await say("下面是一个人正在养的想法：\n\n"+list+
      "\n\n挑一个，今天最该动它。只回 JSON："+'{"id":"…","why":"…"}\n'+
      "why 一句话，说清为什么是它——要具体到这个想法本身，比如它停在哪一步、哪一句还没答。"+
      "不要说「因为它最久没更新」这种谁都能说的话。", { json:true, tier:"quick" });
    if(r && r.id && live.some(i=>i.id===r.id))
      return { id:r.id, why:String(r.why||"").slice(0,200) };
  }catch(e){}
  const o=live.slice().sort((a,b)=>lastAt(a)-lastAt(b))[0];
  return { id:o.id, why:"它停得最久，"+ago(lastAt(o))+"没动过。" };
}
/* 哪两个能撞 */
async function agPair(){
  const live=S.ideas.filter(i=>i.now||i.seed);
  if(live.length<2) return null;
  if(!AI){ const a=live[0], b=live[1];
    return { a:a.id, b:b.id, q:"把「"+b.title+"」和这个放一起。它们能凑成第三个东西吗？" }; }
  try{
    const list=live.slice(0,16).map(i=>"id="+i.id+" 「"+i.title+"」："+
      String(i.now||i.seed).slice(0,140)).join("\n");
    const r=await say("下面是一个人正在养的想法：\n\n"+list+
      "\n\n挑两个放一起会撞出东西的。只回 JSON："+'{"a":"…","b":"…","q":"…"}\n'+
      "a、b 是两个 id。q 是一句话，问他这两个合起来能变成什么——要点出它们各自的具体东西，"+
      "不要问「它们有什么共同点」这种废话。挑的两个越不像越好，但要说得出为什么。", { json:true });
    if(r && r.a && r.b && r.a!==r.b && live.some(i=>i.id===r.a) && live.some(i=>i.id===r.b))
      return { a:r.a, b:r.b, q:String(r.q||"").slice(0,300) };
  }catch(e){}
  const a=live[0], b=live[1];
  return { a:a.id, b:b.id, q:"把「"+b.title+"」和这个放一起。它们能凑成第三个东西吗？" };
}
/* 凉之前推一把 */
async function agChill(it, why){
  return await say("一个人正要放弃这个想法：\n\n"+ideaCtx(it)+
    "\n\n他写的放弃理由是：\n"+why+
    "\n\n问他一句话：这真的是想法本身不成立，还是只是今天没劲、或者卡在某个具体的地方？"+
    "要贴着他写的理由来问，指出他理由里最可疑的那半句。不劝他留下，也不替他决定。"+NOSLOP);
}

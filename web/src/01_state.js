var YD = globalThis.YD;

/* ================== 状态 ================== */
const DAY = 86400000;
function defaultConf(){
  return { models:[{ id:"m0", name:"Claude", kind:"claude", base:"", key:"", model:"" }],
           route:{ ask:"m0", angle:"m0", collide:"m0", rewrite:"m0" },
           sharp:"normal", len:"one", seeGrew:true, seeOthers:true };
}
function seedState(){
  const n = Date.now();
  return {
    ideas:[
      { id:"s1", title:"一间只在下雨天开门的店",
        seed:"如果有家店只在下雨天开门，会是什么店？",
        now:"一间只在落雨时开的小铺。晴天锁门，雨天亮灯。\n卖什么反而不重要——「今天它开了」这件事本身变成一条消息。附近的人会因为下雨想起它，这才是核心。",
        grew:[
          { kind:"ask", q:"那个人现在是怎么凑合的？",
            a:"下雨天大家其实无处可去，要么回家要么钻商场。没有一个地方是「因为下雨才存在」的。", at:n-13*DAY, by:"Claude" },
          { kind:"angle", q:"假装它死了。写一句讣告，说明死因。",
            a:"死于连续四十天没下雨。老板在门上贴了张纸：以后阴天也开。然后它就不特别了。", at:n-11*DAY, by:"Claude" },
          { kind:"collide", q:"把「复印店」硬塞进这个想法里。",
            a:"如果它本来就是间复印店呢？雨天来复印，顺手把湿掉的东西烘一烘。突然就没那么玄了，反而更站得住。", at:n-9*DAY, by:"Claude" }
        ], created:n-16*DAY },
      { id:"s2", title:"把每天走过的路画成一条线",
        seed:"一年下来，这条线会是什么形状？", now:"", grew:[], created:n-DAY }
    ],
    sparks:[
      { id:"k1", text:"图书馆里能不能借「一个下午的安静」", at:n-3*DAY },
      { id:"k2", text:"路灯如果记得每天从它下面走过的人", at:n-11*DAY }
    ],
    cold:[
      { id:"c1", title:"只有我和三个朋友的社交软件",
        why:"聊到第三次才发现：我们不缺一个软件，缺的是一个定期见面的理由。方向一开始就错了——但这个发现比原来那个想法值钱。",
        at:n-40*DAY }
    ],
    conf: defaultConf(), v:"today", tab:"live", cur:null, today:null
  };
}
const LS = "yang.v1";
function load(){ try{ const s=localStorage.getItem(LS); return s?JSON.parse(s):null; }catch(e){ return null; } }
let S = load();
let FRESH = !S;
if(!S) S = { ideas:[], sparks:[], cold:[], conf:defaultConf(), v:"today", tab:"live", cur:null, today:null };
if(!S.sparks) S.sparks = [];
if(!S.conf) S.conf = defaultConf();
if(!S.tab) S.tab = "live";

/* ================== 工具 ================== */
function el(t,c,x){ const e=document.createElement(t); if(c)e.className=c; if(x!=null)e.textContent=x; return e; }
function ago(ts){ const d=Math.floor((Date.now()-ts)/DAY);
  if(d<=0)return"今天"; if(d===1)return"昨天"; if(d<30)return d+" 天前"; return Math.floor(d/30)+" 个月前"; }
function cur(){ return S.ideas.find(i=>i.id===S.cur); }
function uid(p){ return (p||"i")+Math.random().toString(36).slice(2,8); }
function pick(pool,used){ const left=pool.filter(p=>!used.includes(p));
  const from=left.length?left:pool; return from[Math.floor(Math.random()*from.length)]; }
function lastAt(i){ return i.grew && i.grew.length ? i.grew[i.grew.length-1].at : i.created; }
function today(){ const d=new Date(), z=n=>("0"+n).slice(-2);
  return ""+d.getFullYear()+z(d.getMonth()+1)+z(d.getDate()); }
function svgIcon(d,size){
  const s=document.createElementNS("http://www.w3.org/2000/svg","svg");
  s.setAttribute("viewBox","0 0 24 24"); s.setAttribute("width",size||21); s.setAttribute("height",size||21);
  s.setAttribute("fill","none"); s.setAttribute("stroke","currentColor");
  s.setAttribute("stroke-width","1.5"); s.setAttribute("stroke-linecap","round");
  s.setAttribute("stroke-linejoin","round");
  d.forEach(p=>{ const e=document.createElementNS("http://www.w3.org/2000/svg",p[0]);
    for(const k in p[1]) e.setAttribute(k,p[1][k]); s.appendChild(e); });
  return s;
}
const IC = {
  today:[["circle",{cx:12,cy:12,r:8.2}],["path",{d:"M12 7.6V12l2.9 1.9"}]],
  ideas:[["path",{d:"M4 6.5h16"}],["path",{d:"M4 12h16"}],["path",{d:"M4 17.5h10"}]],
  stars:[["circle",{cx:6,cy:7.5,r:2.1}],["circle",{cx:17.4,cy:10.4,r:2.1}],
         ["circle",{cx:10.2,cy:18,r:2.1}],["path",{d:"M8 8.1l7.4 1.9"}],["path",{d:"M15.9 12.2l-4 4.1"}]],
  data:[["path",{d:"M4 7c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3z"}],
        ["path",{d:"M4 7v10c0 1.7 3.6 3 8 3s8-1.3 8-3V7"}],["path",{d:"M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"}]],
  mic:[["path",{d:"M12 3.5a2.6 2.6 0 0 1 2.6 2.6v5.6a2.6 2.6 0 1 1-5.2 0V6.1A2.6 2.6 0 0 1 12 3.5z"}],
       ["path",{d:"M5.6 11.2a6.4 6.4 0 0 0 12.8 0"}],["path",{d:"M12 17.6v3"}]]
};

/* ================== 语音 ================== */
const SRC = window.SpeechRecognition || window.webkitSpeechRecognition;
let VC = { rec:null, ta:null, base:"", why:"", btn:null };
const VERR = {
  "not-allowed":"这个页面拿不到麦克风。手机键盘上有个话筒键，那个在这儿一样能用，而且更稳。",
  "service-not-allowed":"浏览器不让这个页面用语音识别。手机键盘上的话筒键可以顶上。",
  "no-speech":"没听见声音。离近一点再说一次。",
  "audio-capture":"找不到麦克风。",
  "network":"语音识别要联网，这会儿连不上。",
  "aborted":""
};
function voiceStop(){ const r=VC.rec; VC.rec=null; VC.ta=null; if(r){ try{ r.stop(); }catch(e){} } paintMic(); }
function paintMic(){
  document.querySelectorAll("button.mic").forEach(b=>{
    const on = VC.rec && VC.ta === b.__ta;
    b.setAttribute("aria-pressed", String(!!on));
    b.querySelector("span").textContent = on ? "在听…" : "说";
  });
  document.querySelectorAll(".micwhy").forEach(p=>{ p.textContent = VC.why || ""; p.style.display = VC.why ? "" : "none"; });
}
function voiceStart(ta){
  if(!SRC) return;
  let r; try{ r = new SRC(); }catch(e){ VC.why="这个浏览器起不了语音。"; paintMic(); return; }
  r.lang="zh-CN"; r.interimResults=true; r.continuous=true;
  VC.base = ta.value ? ta.value.replace(/\s+$/,"") + (ta.value.trim()?" ":"") : "";
  let fin="";
  r.onresult=(e)=>{
    let itm="";
    for(let i=e.resultIndex;i<e.results.length;i++){
      const t=e.results[i][0].transcript;
      if(e.results[i].isFinal) fin+=t; else itm+=t;
    }
    ta.value = VC.base + fin + itm;
    ta.dispatchEvent(new Event("input",{bubbles:true}));
    try{ ta.scrollTop = ta.scrollHeight; }catch(e){}
  };
  r.onerror=(e)=>{ const m=VERR[e.error]; VC.why = (m===undefined) ? ("语音出错了："+e.error) : m;
    VC.rec=null; VC.ta=null; paintMic(); };
  r.onend=()=>{ if(VC.rec===r){ VC.rec=null; VC.ta=null; paintMic(); } };
  try{ r.start(); VC.rec=r; VC.ta=ta; VC.why=""; }
  catch(e){ VC.why="启动不了语音。"; }
  paintMic();
}
/* 把一个 textarea 包成「可以说的」——没有语音就给一句实话 */
function speakable(ta, hint){
  const w=el("div","spk"); w.appendChild(ta);
  const row=el("div","spkrow");
  if(SRC){
    const b=el("button","mic"); b.type="button"; b.__ta=ta;
    b.appendChild(svgIcon(IC.mic,17)); b.appendChild(el("span",null,"说"));
    b.setAttribute("aria-pressed","false");
    b.addEventListener("click",()=>{ if(VC.rec && VC.ta===ta) voiceStop(); else { voiceStop(); voiceStart(ta); } });
    row.appendChild(b);
  }
  if(hint!==false) row.appendChild(el("span","spkhint", SRC ? "说完点一下停" : "用键盘上的话筒键也能说"));
  w.appendChild(row);
  const p=el("p","note micwhy"); p.style.display="none"; w.appendChild(p);
  return w;
}

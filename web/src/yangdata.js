/* 养想法 · 数据层：本地库 / 导出 / 导入 / 校验 / 加盐签名
   纯逻辑，不碰 DOM，不碰 IndexedDB —— 可以在 node 里直接跑测试。 */
(function (g) {
"use strict";

var FMT = "yang.jsonl";     // 文件族
var V   = 3;                // 当前格式版本
var KDF_ITER = 210000;
var TE = new TextEncoder(), TD = new TextDecoder();
var SUB = (g.crypto && g.crypto.subtle) ? g.crypto.subtle : null;

/* ---------------- 小工具 ---------------- */
function rand(n){ var a = new Uint8Array(n); g.crypto.getRandomValues(a); return a; }
function b64(u8){ var s=""; for (var i=0;i<u8.length;i++) s+=String.fromCharCode(u8[i]);
  return btoa(s).replace(/\+/g,"-").replace(/\//g,"_").replace(/=+$/,""); }
function unb64(s){
  if (typeof s !== "string" || !/^[A-Za-z0-9_-]*$/.test(s)) return null;
  var t = s.replace(/-/g,"+").replace(/_/g,"/"); while (t.length % 4) t += "=";
  try { var bin = atob(t), u = new Uint8Array(bin.length);
        for (var i=0;i<bin.length;i++) u[i]=bin.charCodeAt(i); return u; } catch(e){ return null; }
}
function hex(u8){ var s=""; for (var i=0;i<u8.length;i++) s+=("0"+u8[i].toString(16)).slice(-2); return s; }
function cat(){ var t=0,i,a=arguments; for(i=0;i<a.length;i++) t+=a[i].length;
  var o=new Uint8Array(t),p=0; for(i=0;i<a.length;i++){ o.set(a[i],p); p+=a[i].length; } return o; }

/* 规范化 JSON：键排序、无空白。签名必须对规范化结果做，否则键序一变签名就废。 */
function canon(x){
  if (x === null || typeof x !== "object") return JSON.stringify(x);
  if (Array.isArray(x)) return "[" + x.map(canon).join(",") + "]";
  var ks = Object.keys(x).filter(function(k){ return x[k] !== undefined; }).sort();
  return "{" + ks.map(function(k){ return JSON.stringify(k) + ":" + canon(x[k]); }).join(",") + "}";
}
async function sha256(u8){ return new Uint8Array(await SUB.digest("SHA-256", u8)); }

/* ---------------- 加盐签名 ---------------- */
/* 每行一条指纹：sha256(salt ‖ "r" ‖ 规范化行) 取前 8 字节。
   整份一条指纹：sha256(salt ‖ "f" ‖ 所有行原文)。
   盐每次导出重新生成——同样的数据两次导出，指纹不同，抄不过去。 */
async function lineTag(salt, obj){
  var o = {}; for (var k in obj) if (k !== "h") o[k] = obj[k];
  return hex(await sha256(cat(salt, TE.encode("r"), TE.encode(canon(o))))).slice(0, 16);
}
async function fileTag(salt, lines){
  return hex(await sha256(cat(salt, TE.encode("f"), TE.encode(lines.join("\n")))));
}
async function deriveKey(pass, salt){
  var base = await SUB.importKey("raw", TE.encode(pass), "PBKDF2", false, ["deriveKey"]);
  return SUB.deriveKey({ name:"PBKDF2", salt:salt, iterations:KDF_ITER, hash:"SHA-256" },
    base, { name:"AES-GCM", length:256 }, false, ["encrypt","decrypt"]);
}

/* ---------------- 记录：从内存态拆出来 ---------------- */
var KINDS = ["ask","angle","collide","note"];
function records(state, opts){
  var out = [], keepKeys = !!(opts && opts.keepKeys);
  (state.ideas || []).forEach(function (i) {
    out.push({ t:"idea", id:i.id, title:i.title, seed:i.seed||"", now:i.now||"",
      created:i.created, grew:(i.grew||[]).map(function(gr){
        return { kind:gr.kind, q:gr.q, a:gr.a, at:gr.at, by:gr.by||"" }; }) });
  });
  (state.sparks || []).forEach(function (k) {
    out.push({ t:"spark", id:k.id, text:k.text, at:k.at });
  });
  (state.cold || []).forEach(function (c) {
    out.push({ t:"cold", id:c.id, title:c.title, why:c.why, at:c.at });
  });
  if (state.conf) {
    var c = JSON.parse(JSON.stringify(state.conf));
    (c.models || []).forEach(function (m) {
      if (!keepKeys) { m.key = ""; m.keyDropped = true; }
    });
    c.t = "conf"; out.push(c);
  }
  return out;
}

/* ---------------- 导出 ---------------- */
/* opts: {pass:"口令"|null}。给了口令就整条加密（模型钥匙才会一起带走）。 */
async function exportJSONL(state, opts) {
  opts = opts || {};
  if (!SUB) throw new Error("这个环境没有 Web Crypto，签不了名，也就不该导出。");
  var pass = opts.pass || null;
  var salt = rand(16);
  var recs = records(state, { keepKeys: !!pass });
  var key = pass ? await deriveKey(pass, salt) : null;
  var lines = [], counts = { idea:0, spark:0, cold:0, conf:0 };

  for (var i = 0; i < recs.length; i++) {
    var r = recs[i];
    counts[r.t] = (counts[r.t] || 0) + 1;
    if (key) {
      var iv = rand(12);
      var ct = new Uint8Array(await SUB.encrypt({ name:"AES-GCM", iv:iv, additionalData:salt },
        key, TE.encode(canon(r))));
      var e = { t:"enc", iv:b64(iv), ct:b64(ct) };
      e.h = await lineTag(salt, e);
      lines.push(JSON.stringify(e));
    } else {
      r.h = await lineTag(salt, r);
      lines.push(JSON.stringify(r));
    }
  }
  var head = {
    t:"head", fmt:FMT, v:V, app:"养想法", at:Date.now(),
    enc: pass ? "aes-gcm-256" : "none",
    kdf: pass ? { name:"PBKDF2", hash:"SHA-256", iter:KDF_ITER } : undefined,
    salt: b64(salt), counts: counts, keys: !!pass,
    digest: await fileTag(salt, lines)
  };
  return { text: JSON.stringify(head) + "\n" + lines.join("\n") + "\n",
           counts: counts, encrypted: !!pass };
}

/* ---------------- 校验 ---------------- */
var MAX = { title:200, seed:2000, now:20000, why:20000, q:1000, a:20000, grew:500, recs:20000 };
var T0 = Date.UTC(2015,0,1);
function isId(v){ return typeof v === "string" && /^[A-Za-z0-9_-]{1,64}$/.test(v); }
function isTs(v){ return Number.isInteger(v) && v >= T0 && v <= Date.now() + 86400000 * 2; }
function str(v, max){ return typeof v === "string" && v.length <= max; }
function safeUrl(v){
  if (typeof v !== "string" || !v) return true;
  return /^https?:\/\//i.test(v);
}

function checkRecord(r, ln) {
  var e = [];
  function bad(msg){ e.push({ line: ln, msg: msg }); }
  if (!r || typeof r !== "object" || Array.isArray(r)) { bad("这一行不是一条记录。"); return e; }
  if (r.t === "idea") {
    if (!isId(r.id)) bad("想法的 id 不对（只能是字母、数字、- 和 _，1–64 位）。");
    if (!str(r.title,MAX.title) || !r.title.trim()) bad("想法缺标题，或标题超过 " + MAX.title + " 字。");
    if (!str(r.seed,MAX.seed)) bad("「最初那句」不是文本，或超过 " + MAX.seed + " 字。");
    if (!str(r.now,MAX.now)) bad("「现在它是什么」不是文本，或超过 " + MAX.now + " 字。");
    if (!isTs(r.created)) bad("想法的创建时间不是一个说得通的时间戳。");
    if (!Array.isArray(r.grew)) bad("生长记录不是一个列表。");
    else if (r.grew.length > MAX.grew) bad("生长记录超过 " + MAX.grew + " 条。");
    else r.grew.forEach(function (x, i) {
      var at = "第 " + (i+1) + " 条生长记录";
      if (!x || typeof x !== "object") return bad(at + "不是一条记录。");
      if (KINDS.indexOf(x.kind) < 0) bad(at + "的类型「" + x.kind + "」不认识，只能是 " + KINDS.join(" / ") + "。");
      if (!str(x.q,MAX.q) || !x.q.trim()) bad(at + "没有问题原文。");
      if (!str(x.a,MAX.a) || !x.a.trim()) bad(at + "没有你的回答。");
      if (!isTs(x.at)) bad(at + "的时间不对。");
    });
  } else if (r.t === "spark") {
    if (!isId(r.id)) bad("念头的 id 不对（只能是字母、数字、- 和 _，1–64 位）。");
    if (!str(r.text, MAX.seed) || !r.text.trim()) bad("念头是空的，或超过 " + MAX.seed + " 字。");
    if (!isTs(r.at)) bad("念头的时间不对。");
  } else if (r.t === "cold") {
    if (!isId(r.id)) bad("凉了的想法 id 不对。");
    if (!str(r.title,MAX.title) || !r.title.trim()) bad("凉了的想法缺标题。");
    if (!str(r.why,MAX.why) || !r.why.trim()) bad("缺「为什么凉了」——这一句是这条记录里最值钱的部分，不能空。");
    if (!isTs(r.at)) bad("时间不对。");
  } else if (r.t === "conf") {
    if (r.models !== undefined && !Array.isArray(r.models)) bad("模型配置不是一个列表。");
    (r.models || []).forEach(function (m, i) {
      if (!m || typeof m !== "object") return bad("第 " + (i+1) + " 个模型不是一条配置。");
      if (!str(m.name,120) || !m.name) bad("第 " + (i+1) + " 个模型没有名字。");
      if (!safeUrl(m.base)) bad("第 " + (i+1) + " 个模型的地址不是 http/https，不收。");
      if (!str(m.model,200)) bad("第 " + (i+1) + " 个模型的模型名不是文本。");
    });
    if (r.route !== undefined && (typeof r.route !== "object" || !r.route)) bad("动作路由不是一个对象。");
  } else {
    bad("不认识的记录类型「" + String(r.t) + "」。");
  }
  return e;
}

/* ---------------- 导入 ---------------- */
/* 返回 {ok, head, recs, errors, warnings, stats}。不改任何状态——先给人看清楚再说。 */
async function parseJSONL(text, opts) {
  opts = opts || {};
  var errors = [], warnings = [];
  function fail(msg){ errors.push({ line:0, msg:msg }); return { ok:false, errors:errors, warnings:warnings }; }
  if (!SUB) return fail("这个环境没有 Web Crypto，验不了签名。");
  if (typeof text !== "string" || !text.trim()) return fail("文件是空的。");
  if (text.length > 40 * 1024 * 1024) return fail("文件超过 40MB，先确认没选错文件。");

  var raw = text.split(/\r?\n/).filter(function (s) { return s.trim() !== ""; });
  var head;
  try { head = JSON.parse(raw[0]); } catch (e) { return fail("第一行不是 JSON。这份文件多半不是养想法导出的。"); }
  if (!head || head.t !== "head" || head.fmt !== FMT)
    return fail("这不是养想法的导出文件（第一行没有 " + FMT + " 的标记）。");
  if (!Number.isInteger(head.v) || head.v < 1)
    return fail("文件没写版本号，不敢导。");
  if (head.v > V)
    return fail("这份文件是更新版本的养想法导出的（v" + head.v + "），这一版只认到 v" + V + "。先升级再导入。");
  var salt = unb64(head.salt);
  if (!salt || salt.length < 16) return fail("文件里的盐值不对或缺失，验不了签名。");
  if (head.enc !== "none" && head.enc !== "aes-gcm-256")
    return fail("不认识的加密方式「" + String(head.enc) + "」。");

  var body = raw.slice(1);
  if (body.length > MAX.recs) return fail("记录超过 " + MAX.recs + " 条，先拆开再导。");

  var got = await fileTag(salt, body);
  if (got !== head.digest)
    return fail("整份文件的指纹对不上。文件在导出之后被改过，或者传输时坏了。别导——找一份没动过的。");

  var key = null;
  if (head.enc === "aes-gcm-256") {
    if (!opts.pass) return { ok:false, needPass:true, head:head, errors:errors, warnings:warnings };
    if (!head.kdf || head.kdf.name !== "PBKDF2" || head.kdf.hash !== "SHA-256"
        || !Number.isInteger(head.kdf.iter) || head.kdf.iter < 10000 || head.kdf.iter > 5000000)
      return fail("加密参数不对或被改过。");
    try { key = await deriveKey(opts.pass, salt); } catch (e) { return fail("算不出密钥。"); }
  }

  var recs = [], seen = Object.create(null), counts = { idea:0, spark:0, cold:0, conf:0 };
  for (var i = 0; i < body.length; i++) {
    var ln = i + 2, obj;
    try { obj = JSON.parse(body[i]); } catch (e) { errors.push({ line:ln, msg:"这一行不是 JSON。" }); continue; }
    if (!obj || typeof obj !== "object") { errors.push({ line:ln, msg:"这一行不是一条记录。" }); continue; }

    var tag = await lineTag(salt, obj);
    if (obj.h !== tag) { errors.push({ line:ln, msg:"这一行的指纹对不上，被改过。" }); continue; }

    var r = obj;
    if (obj.t === "enc") {
      if (!key) { errors.push({ line:ln, msg:"这一行是加密的，但文件头说没加密。" }); continue; }
      var iv = unb64(obj.iv), ct = unb64(obj.ct);
      if (!iv || iv.length !== 12 || !ct) { errors.push({ line:ln, msg:"加密块的格式不对。" }); continue; }
      try {
        var pt = await SUB.decrypt({ name:"AES-GCM", iv:iv, additionalData:salt }, key, ct);
        r = JSON.parse(TD.decode(pt));
      } catch (e) {
        return fail("口令不对，或者这份文件的加密内容被改过。（AES-GCM 解不开就是解不开，没有「差一点」。）");
      }
    } else if (key) { errors.push({ line:ln, msg:"文件头说加密了，但这一行是明文。" }); continue; }

    var es = checkRecord(r, ln);
    if (es.length) { errors = errors.concat(es); continue; }
    if (r.t !== "conf") {
      if (seen[r.t + ":" + r.id]) { errors.push({ line:ln, msg:"id「" + r.id + "」在文件里出现了不止一次。" }); continue; }
      seen[r.t + ":" + r.id] = 1;
    }
    counts[r.t] = (counts[r.t] || 0) + 1;
    recs.push(r);
  }

  ["idea","spark","cold","conf"].forEach(function (k) {
    var want = head.counts && head.counts[k];
    if (Number.isInteger(want) && want !== counts[k])
      warnings.push("文件头说有 " + want + " 条 " + k + "，实际读出 " + counts[k] + " 条。");
  });
  if (head.enc === "none" && head.keys)
    warnings.push("文件头说带了模型钥匙，但它没加密。不该这样导。");
  if (head.enc === "none")
    warnings.push("这份是明文导出，模型钥匙没有带出来——导入后要重新填一次。");

  return { ok: errors.length === 0, head: head, recs: recs, counts: counts,
           errors: errors, warnings: warnings };
}

/* ---------------- 落回状态 ---------------- */
/* mode: "merge"（按 id 合，谁新留谁）| "replace"（整个换掉） */
function apply(cur, recs, mode) {
  var inIdeas = [], inSparks = [], inCold = [], conf = null;
  recs.forEach(function (r) {
    if (r.t === "idea") inIdeas.push({ id:r.id, title:r.title, seed:r.seed, now:r.now,
      created:r.created, grew:r.grew.map(function(x){
        return { kind:x.kind, q:x.q, a:x.a, at:x.at, by:x.by||"" }; }) });
    else if (r.t === "spark") inSparks.push({ id:r.id, text:r.text, at:r.at });
    else if (r.t === "cold") inCold.push({ id:r.id, title:r.title, why:r.why, at:r.at });
    else if (r.t === "conf") { conf = r; delete conf.t; delete conf.h; }
  });
  if (mode === "replace")
    return { ideas: inIdeas, sparks: inSparks, cold: inCold, conf: conf || cur.conf || null,
             report: { added: inIdeas.length + inSparks.length + inCold.length, updated: 0, kept: 0 } };

  var byId = {}, rep = { added:0, updated:0, kept:0 };
  function last(i){ return i.grew && i.grew.length ? i.grew[i.grew.length-1].at : i.created; }
  (cur.ideas || []).forEach(function (i) { byId[i.id] = i; });
  inIdeas.forEach(function (i) {
    var old = byId[i.id];
    if (!old) { byId[i.id] = i; rep.added++; }
    else if (last(i) > last(old)) { byId[i.id] = i; rep.updated++; }
    else rep.kept++;
  });
  var sId = {}; (cur.sparks || []).forEach(function (k) { sId[k.id] = k; });
  inSparks.forEach(function (k) {
    if (!sId[k.id]) { sId[k.id] = k; rep.added++; }
    else if (k.at > sId[k.id].at) { sId[k.id] = k; rep.updated++; }
    else rep.kept++;
  });
  var cId = {}; (cur.cold || []).forEach(function (c) { cId[c.id] = c; });
  inCold.forEach(function (c) {
    if (!cId[c.id]) { cId[c.id] = c; rep.added++; }
    else if (c.at > cId[c.id].at) { cId[c.id] = c; rep.updated++; }
    else rep.kept++;
  });
  return {
    ideas:  Object.keys(byId).map(function (k) { return byId[k]; }),
    sparks: Object.keys(sId).map(function (k) { return sId[k]; }),
    cold:   Object.keys(cId).map(function (k) { return cId[k]; }),
    conf:  conf || cur.conf || null, report: rep
  };
}

g.YD = { FMT:FMT, V:V, canon:canon, exportJSONL:exportJSONL, parseJSONL:parseJSONL,
         apply:apply, checkRecord:checkRecord, records:records, b64:b64, unb64:unb64 };
})(typeof globalThis !== "undefined" ? globalThis : this);

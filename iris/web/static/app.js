/* Iris Web 前端：输入 -> 画像问卷 -> 决策卡（假设编辑 + 重算历史）。
 * M8：用户名+密码登录/注册（本地哈希）；我的数据 = 决策历史（完整快照，
 * 可一键还原查看）/ 关注商品 / 分品类画像自动预填；支持导出 JSON 与注销。
 * 交互约定：点选选项 = 自动进入下一题（260ms 高亮反馈）；可点「上一题」修改；
 * 最后一题点选后自动提交出卡；已登录用户的历史画像自动预填，可一键沿用。
 */
"use strict";

var S = { product: null, sku_id: null, questions: [], flow: null,
          answers: {}, session_id: null, card: null, profile: null, hist: [],
          user: null, watchMap: {}, savedState: "anon", dirty: false,
          snap: null, autoStartQ: false };
var LAST_MAIN = "view-input";

var $ = function (id) { return document.getElementById(id); };
function esc(x) {
  return String(x == null ? "" : x).replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
function token() {
  try { return localStorage.getItem("iris.token") || ""; } catch (e) { return ""; }
}
function loggedIn() { return !!token(); }
function api(method, path, body) {
  var opt = { method: method || "GET", headers: {} };
  var t = token();
  if (t) { opt.headers["X-Iris-Token"] = t; }
  if (body !== undefined) {
    opt.headers["Content-Type"] = "application/json";
    opt.body = JSON.stringify(body);
  }
  return fetch(path, opt).then(function (r) {
    return r.text().then(function (txt) {
      var j = null;
      if (txt) { try { j = JSON.parse(txt); } catch (e) { j = null; } }
      if (!r.ok) { throw new Error((j && (j.detail || j.error)) || ("HTTP " + r.status)); }
      return j;
    });
  });
}
function isAuthErr(e) {
  var m = String(e && e.message || "");
  return m.indexOf("401") >= 0 || m.indexOf("未登录") >= 0;
}
function show(id) {
  ["view-input", "view-questions", "view-card", "view-me"].forEach(function (v) {
    var el = $(v);
    if (el) { el.classList.toggle("hidden", v !== id); }
  });
  var isMain = (id === "view-input" || id === "view-questions" || id === "view-card");
  var root = $("flow-root");
  if (root) { root.classList.toggle("hidden", !isMain); }
  var steps = $("steps"); if (steps) { steps.classList.toggle("hidden", !isMain); }
  if (isMain) { LAST_MAIN = id; }
  window.scrollTo(0, 0);
}
function setStep(i) {
  ["step-i", "step-q", "step-c"].forEach(function (s, k) { $(s).classList.toggle("on", k < i); });
}
function setNav(view) {
  var cur = view === "view-me" ? "me" : "flow";
  document.querySelectorAll(".sbtn[data-view]").forEach(function (b) {
    b.classList.toggle("on", b.getAttribute("data-view") === cur);
  });
  var f = $("flow-root"); if (f) { f.classList.toggle("hidden", view === "view-me" || !view); }
  var m = $("view-me"); if (m) { m.classList.toggle("hidden", view !== "view-me"); }
}

/* ---------- 用户会话（登录 / 登出 / 顶栏） ---------- */
function rememberUser(uname, t) {
  try {
    localStorage.setItem("iris.user", uname);
    localStorage.setItem("iris.token", t);
  } catch (e) {}
  S.user = uname; S.watchMap = {};
}
function forgetUser() {
  try {
    localStorage.removeItem("iris.user");
    localStorage.removeItem("iris.token");
  } catch (e) {}
  S.user = null; S.watchMap = {};
}
function refreshUserBar() {
  var on = !!S.user;
  $("sb-ub-name").textContent = S.user || "";
  $("sb-ub-name").classList.toggle("hidden", !on);
  $("btn-login").classList.toggle("hidden", on);
  $("btn-logout").classList.toggle("hidden", !on);
}
function authExpired() {
  forgetUser(); refreshUserBar();
  show("view-input"); setStep(1);
  $("resolve-out").innerHTML = '<p class="tip">登录已过期，请重新登录（游客模式仍可使用）。</p>';
}
function applyLogin(uname, t) {
  rememberUser(uname, t); refreshUserBar();
  var back = S.afterAuth || LAST_MAIN || "view-input";
  S.afterAuth = null;
  if (back === "view-me") { openMe(); return; }
  if (back === "view-card") {
    if (S.card) { show("view-card"); setStep(3); refreshCard(); return; }
    back = "view-input";
  }
  show(back);
  if (back === "view-questions") { setStep(2); }
  else if (back === "view-card") { setStep(3); }
  else { setStep(1); }
  if (back === "view-input" && S.card) {
    $("resolve-out").innerHTML = '<p class="tip">已登录为「' + esc(S.user) +
      '」：刚才那张卡可点卡片下方按钮存入历史，或直接重新出卡（自动存档）。</p>';
  }
}
function doLogout() {
  api("POST", "/api/auth/logout").catch(function () {}).then(function () {
    forgetUser(); refreshUserBar();
    S.snap = null; S.savedState = "anon"; S.dirty = false;
    show("view-input"); setStep(1);
    $("resolve-out").innerHTML = '<p class="tip">已退出登录。游客模式照常可用，但决策不会自动存档。</p>';
  });
}
function initSession() {
  if (!token()) { refreshUserBar(); return; }
  api("GET", "/api/me").then(function (info) {
    S.user = info.username; refreshUserBar();
  }).catch(function () { forgetUser(); refreshUserBar(); });
}

/* ---------- 登录 / 注册 视图 ---------- */
var AUTH = { mode: "login" };
function authLabels() {
  var reg = AUTH.mode === "register";
  $("auth-title").textContent = reg ? "注册" : "登录";
  $("auth-sub").textContent = reg
    ? "注册后：每次出卡自动存档，同品类免重填，还能关注商品。"
    : "登录后：每次出卡自动存档，同品类免重填，还能关注商品。";
  $("btn-auth-go").textContent = reg ? "注册并登录" : "登录";
  $("btn-auth-toggle").textContent = reg ? "已有账号？去登录" : "没有账号？去注册";
}
function openAuth(mode) {
  S.afterAuth = LAST_MAIN || "view-input";
  AUTH.mode = mode || "login";
  $("auth-user").value = ""; $("auth-pass").value = "";
  $("auth-err").textContent = "";
  authLabels();
  $("auth-modal").classList.remove("hidden");
  setTimeout(function () { $("auth-user").focus(); }, 40);
}
function closeAuth() {
  $("auth-modal").classList.add("hidden");
}
function doAuth() {
  var u = $("auth-user").value.trim();
  var p = $("auth-pass").value;
  var url = AUTH.mode === "register" ? "/api/auth/register" : "/api/auth/login";
  $("btn-auth-go").disabled = true;
  $("auth-err").textContent = "";
  api("POST", url, { username: u, password: p }).then(function (j) {
    closeAuth();
    applyLogin(j.username, j.token);
  }).catch(function (e) {
    $("auth-err").textContent = e.message;
  }).then(function () { $("btn-auth-go").disabled = false; });
}

/* ---------- 第一步：解析 ---------- */
function resolveText(text) {
  S.autoStartQ = false;
  $("btn-resolve").disabled = true;
  $("resolve-out").innerHTML = '<p class="tip">解析中…</p>';
  api("POST", "/api/resolve", { text: text }).then(function (j) {
    $("resolve-out").innerHTML = "";
    if (!j.product || !j.product.category) {
      $("resolve-out").innerHTML =
        '<div class="panel"><p>' + esc(j.message || "未识别品类") + '</p>' +
        '<p><label>商品名 <input id="m-name" size="24"></label> &nbsp; ' +
        '<label>品类 <select id="m-cat">' +
        '<option>显卡</option><option>药品</option><option>手机</option>' +
        '<option>笔记本</option><option>家电</option></select></label> &nbsp; ' +
        '<button id="m-go">继续（手动确认）</button></p></div>';
      $("m-go").onclick = function () {
        S.autoStartQ = true;
        api("POST", "/api/resolve", { text: text, name: $("m-name").value, category: $("m-cat").value })
          .then(enterResolved);
      };
      return;
    }
    enterResolved(j);
  }).catch(function (e) {
    $("resolve-out").innerHTML = '<p class="tip">解析失败：' + esc(e.message) + "</p>";
  }).then(function () { $("btn-resolve").disabled = false; });
}
function enterResolved(j) {
  S.product = j.product; S.sku_id = j.sku_id; S.questions = j.questions || [];
  S.flow = j.flow; S.answers = {}; S.card = null; S.snap = null; S.hist = [];
  S.session_id = null; S.dirty = false; S.savedState = "anon";
  var hitTxt = S.sku_id ? "命中 demo 库 SKU：" + S.sku_id
                        : "（demo 库无此型号价格数据 → 只跑画像/闸门流程）";
  $("resolve-out").innerHTML =
    '<div class="panel"><b>' + esc(S.product.name) + "</b>　品类：" +
    esc(S.product.category) + "　流程：" +
    (S.flow === "essential" ? "必需闸门（3 题）" : "完整时机问卷（" +
     (S.questions || []).length + " 屏，含贴现 3 小题）") +
    '　<span class="muted">' + esc(hitTxt) + "</span>" +
    (j.message ? "<p class='muted'>" + esc(j.message) + "</p>" : "") +
    (S.questions.length ? '<p><button id="g-start">开始问答 →</button></p>' : "") +
    "</div>";
  var b = $("g-start");
  if (b) {
    b.onclick = function () { startQuestions(); };
    if (S.autoStartQ) { S.autoStartQ = false; startQuestions(); }
  }
}
function chipFill() {
  document.querySelectorAll(".chip").forEach(function (c) {
    c.onclick = function () { $("text").value = c.getAttribute("data-ex"); };
  });
}
function startRerun(product) {
  $("text").value = (product && product.name) ? product.name : "";
  S.questions = []; S.card = null; S.snap = null; S.session_id = null;
  S.dirty = false; S.hist = []; S.savedState = "anon";
  S.product = product || null;
  show("view-input"); setStep(1);
  S.autoStartQ = true;
  resolveText($("text").value);
}

/* ---------- 第二步：画像问卷（点选自动下一题；登录后历史画像预填） ---------- */
var Q = { items: [], idx: 0, picked: {}, timer: null, prefilled: 0 };
function startQuestions() {
  Q.items = [];
  (S.questions || []).forEach(function (q) {
    if (q.type === "group") {
      (q.items || []).forEach(function (it) {
        Q.items.push({ text: it.text, id: it.id, options: it.options });
      });
    } else { Q.items.push(q); }
  });
  Q.idx = 0; Q.picked = {}; Q.prefilled = 0;
  show("view-questions");
  setStep(2);
  var flowTxt = S.flow === "essential"
    ? "必需品类：时点不重要 —— 回答 3 题后直达「直接买 + 渠道比价」结论"
    : "完整时机问卷：" + Q.items.length + " 题（含 3 道「等多久换折扣」测评题）";
  $("q-flow").textContent = "商品：" + S.product.name + " ｜ " + flowTxt;
  if (loggedIn() && S.product && S.product.category) {
    api("GET", "/api/me/profiles?category=" + encodeURIComponent(S.product.category))
      .then(function (j) { applyPrefill((j && j.answers) || null); })
      .catch(function () { renderQ(); });
  } else { renderQ(); }
}
function validOption(q, v) {
  return (q.options || []).some(function (o) {
    return (Array.isArray(o) ? o[1] : o) === v;
  });
}
function applyPrefill(answers) {
  Q.picked = {}; Q.prefilled = 0;
  if (answers) {
    Q.items.forEach(function (q) {
      var v = answers[q.id];
      if (v != null && validOption(q, v)) { Q.picked[q.id] = v; Q.prefilled++; }
    });
  }
  if (Q.prefilled === Q.items.length) { Q.idx = 0; }
  else {
    Q.idx = 0;
    while (Q.idx < Q.items.length && Q.picked[Q.items[Q.idx].id] != null) { Q.idx++; }
    if (Q.idx >= Q.items.length) { Q.idx = Math.max(0, Q.items.length - 1); }
  }
  renderQ();
}
function prefillNoteHtml() {
  if (Q.idx !== 0 || Q.prefilled === 0) { return ""; }
  if (Q.prefilled === Q.items.length) {
    return '<div class="cond prefill-note"><b>已载入你的历史画像</b>（' + Q.prefilled +
      "/" + Q.items.length + " 题全部沿用上次答案）。" +
      "<button id='btn-prefill-go' class='small'>直接沿用并出卡 →</button>" +
      " <span class='muted'>或改动下方任一选项（自动前进）</span></div>";
  }
  return "<p class='tip'>已用历史画像预填 " + Q.prefilled + " 题（可点「上一题」逐题检查修改）。</p>";
}
function renderQ() {
  var q = Q.items[Q.idx];
  $("q-nav").classList.remove("hidden");
  $("btn-prev").classList.toggle("hidden", Q.idx === 0);
  $("q-body").innerHTML = '<p class="progress">第 ' + (Q.idx + 1) + " / " +
    Q.items.length + " 题（点选选项自动进入下一题，可随时「上一题」修改）</p>" +
    prefillNoteHtml() + '<p class="q-text">' + esc(q.text) + "</p>";
  (q.options || []).forEach(function (o, i) {
    var val = (Array.isArray(o) ? o[1] : o);
    var label = (Array.isArray(o) ? o[0] : o);
    var b = document.createElement("button");
    b.className = "q-opt" + (Q.picked[q.id] === val ? " picked" : "");
    b.type = "button";
    b.textContent = (i + 1) + ". " + label;
    b.onclick = function () {
      Q.picked[q.id] = val;
      document.querySelectorAll(".q-opt").forEach(function (x) { x.classList.remove("picked"); });
      b.classList.add("picked");
      clearTimeout(Q.timer);
      Q.timer = setTimeout(autoAdvance, 260);
    };
    $("q-body").appendChild(b);
  });
  var go = $("btn-prefill-go");
  if (go) { go.onclick = function () { submitAnswers(); }; }
  if (Q.picked[q.id] != null) {
    var cont = document.createElement("button");
    cont.type = "button";
    cont.className = "ghost";
    cont.textContent = (Q.idx < Q.items.length - 1)
      ? "继续 →（不改则直接前进）" : "用当前答案出卡 →";
    cont.onclick = autoAdvance;
    $("q-body").appendChild(cont);
  }
}
function autoAdvance() {
  var q = Q.items[Q.idx];
  if (Q.picked[q.id] == null) { return; }
  if (Q.idx < Q.items.length - 1) { Q.idx++; renderQ(); }
  else { submitAnswers(); }
}
function prevQ() {
  clearTimeout(Q.timer);
  if (Q.idx > 0) { Q.idx--; renderQ(); }
}
function submitAnswers() {
  Q.items.forEach(function (q) { S.answers[q.id] = Q.picked[q.id]; });
  $("q-nav").classList.add("hidden");
  $("q-flow").textContent = "正在计算：历史分位 → P1 频率 → 事件窗口 → 替代矩阵 → 期望值裁决 …";
  $("q-body").innerHTML = '<p class="tip">计算中（demo 数据秒级完成）…</p>';
  api("POST", "/api/answer", { product: S.product, sku_id: S.sku_id, answers: S.answers })
    .then(function (j) {
      S.session_id = j.session_id; S.profile = j.profile; S.hist = [];
      S.dirty = false; S.snap = null;
      S.savedState = j.saved ? "auto" : "anon";
      if (j.card) { S.card = j.card; showCard(j.card); }
      else {
        S.card = null;
        show("view-card"); setStep(3);
        $("no-data").classList.remove("hidden");
        $("no-data").innerHTML =
          '<div class="panel"><h3>流程结论（无价格库，未出量化卡）</h3><p>' +
          esc(j.note || "demo 库暂无该型号数据") + "</p>" +
          '<p class="muted">画像已记录：' + esc(JSON.stringify(j.profile)) + "</p>" +
          '<p class="tip">' + (j.saved
            ? "本次画像与结论已自动存入「我的数据 → 决策历史」。"
            : "游客模式：登录后此类流程也会自动存档。") + "</p></div>";
        $("card-root").innerHTML = "";
      }
    }).catch(function (e) {
      $("q-nav").classList.remove("hidden");
      $("q-flow").textContent = "提交失败：" + e.message + " —— 已保留你的答案，可改选后重试。";
      renderQ();
    });
}

/* ---------- 第三步：决策卡 ---------- */
var LIGHT = { green: "绿 · 现在买", yellow: "黄 · 等 / 换", red: "红 · 别现在买" };
var LIGHT_KEY = { green: "green", yellow: "yellow", red: "red" };
var REC = { buy: "现在买", wait: "先等一等", switch: "换一个买" };
function recTxt(r) { return REC[r] || r; }
function pct1(x) { return x == null ? "--" : (x * 100).toFixed(0) + "%"; }
function pct2(x) { return x == null ? "--" : (x * 100).toFixed(2) + "%"; }
function money(x) { return x == null ? "--" : "¥" + Math.round(x); }

function showCard(card) {
  S.card = card;
  $("no-data").classList.add("hidden");
  show("view-card"); setStep(3);
  $("card-root").innerHTML = renderCard(card, S.profile || {}, S.hist || [], false, S.snap);
  bindCardEvents(card);
}
function refreshCard() {
  if (!S.card) { return; }
  $("card-root").innerHTML = renderCard(S.card, S.profile || {}, S.hist || [], false, S.snap);
  bindCardEvents(S.card);
}
function banner(card) {
  var d = card.decision;
  var k = LIGHT_KEY[d.traffic_light] || "yellow";
  var recTxt0 = recTxt(d.recommendation);
  return '<div class="banner ' + k + '"><div><span class="light-dot ' + k + '"></span>' +
    "<div class='big'>" + recTxt0 + "　" + LIGHT[d.traffic_light] + "</div>" +
    "<div class='mid'>P1（60 天降价≥5% 概率）≈ <b>" +
    pct1(card.p1["60"].probability) + "</b>（n=" + card.p1["60"].n + "）　｜　" +
    "P2（现在买是 60 天内最优决策）≈ <b>" + pct1(d.p2.probability) + "</b>" +
    "</div></div></div>";
}
function kpiRow(card) {
  var st = card.stats, lb = st.lookbacks;
  return '<div class="kpi">' +
    "<div><b>" + st.last_price + "</b><span>现价（元）</span></div>" +
    "<div><b>" + (lb["90"].pct_position * 100).toFixed(0) + "%</b><span>90 天历史分位</span></div>" +
    "<div><b>" + (lb["365"].pct_position * 100).toFixed(0) + "%</b><span>1 年历史分位</span></div>" +
    "<div><b>" + (lb["730"].pct_position * 100).toFixed(0) + "%</b><span>2 年历史分位</span></div>" +
    "</div>";
}
function p1Table(card) {
  var rows = "";
  ["30", "60", "180"].forEach(function (w) {
    var fc = card.p1[w];
    var prob = fc.probability == null ? "样本不足" : pct1(fc.probability);
    var ci = fc.ci95 ? "[" + fc.ci95[0].toFixed(2) + ", " + fc.ci95[1].toFixed(2) + "]" : "—";
    rows += "<tr><td>未来 " + w + " 天降价 ≥5%</td><td>" + prob + "</td><td>" + ci +
      "</td><td>" + fc.n + "</td><td>" + (fc.direction === "down" ? "偏降价" : fc.direction) +
      "</td></tr>";
  });
  return "<table><tr><th>窗口</th><th>P1 概率</th><th>95% CI</th><th>样本 n</th><th>方向</th></tr>" +
    rows + "</table><p class='muted'>[ref: p1.windows + R04 校准口径；同分位段历史频率]</p>";
}
function decompTable(card) {
  var d = card.decision, c = d.decomposition;
  if (!c) { return ""; }
  return "<table><tr><th>期望值分解</th><th>占现价</th><th>金额</th><th>含义</th></tr>" +
    "<tr><td>G 等待收益</td><td>" + pct2(c.saving_pct / 100) + "</td><td>" + money(c.saving_yuan) +
    "</td><td>历史同价位段等满窗口的期望节省（p1.wait_stats）</td></tr>" +
    "<tr><td>U 等待效用损失</td><td>" + pct2(c.u_pct / 100) + "</td><td>" + money(c.u_yuan) +
    "</td><td>强度×享乐×贴现档（R05 §3，A1-A2 待标定）</td></tr>" +
    "<tr><td>R 等待风险</td><td>" + pct2(c.r_pct / 100) + "</td><td>" + money(c.r_yuan) +
    "</td><td>历史涨损 + 供需附加 " + pct2(c.supply_premium_pct / 100) + "</td></tr>" +
    "<tr><td>buffer 缓冲</td><td>" + pct2(c.buffer_pct / 100) + "</td><td>" + money(c.buffer_yuan) +
    "</td><td>随波动率分位加宽（(S,s)，总纲 §1.2）</td></tr>" +
    "<tr><td><b>净期望 net</b></td><td><b>" + pct2(c.net_pct / 100) + "</b></td><td><b>" +
    money(c.net_yuan) + "</b></td><td>net>0 倾向等；否则买</td></tr></table>" +
    "<p class='muted'>[ref: decision.decomposition + 总纲 §2.5 / R05 §3 / D5]</p>";
}
function conditionsHtml(card) {
  return (card.decision.conditions || []).map(function (c) {
    return "<div class='cond'>" + esc(c.text) + "</div>";
  }).join("");
}
function eventsHtml(card) {
  var ev = card.events || {};
  var h = "";
  ["promo", "supply", "launch"].forEach(function (t) {
    var s = ((ev[t] || {}).horizons || {})["60"];
    if (s && s.n) {
      h += "<tr><td>" + t + "</td><td>" + s.n + " 起</td><td>" +
        (s.mean_pct == null ? "--" : (s.mean_pct > 0 ? "+" : "") + s.mean_pct + "%") +
        "</td><td>事件后 60 天相对起点/对照</td></tr>";
    }
  });
  var upcoming = (ev.upcoming || []).map(function (u) {
    return "<span class='chip' title='" + esc(u.summary_text || "") + "'>" +
      u.date + " " + esc(u.title) + "（" + u.days_ahead + " 天后）</span>";
  }).join(" ");
  return (h ? "<table><tr><th>类型</th><th>样本</th><th>60 天窗均值</th><th>口径</th></tr>" + h + "</table>" : "") +
    "<p class='muted'>未来 180 天内事件：" + (upcoming || "无") + "</p>";
}
function altTable(card) {
  var d = card.decision;
  var bestId = d.switch_to ? d.switch_to.sku_id : null;
  var rows = (card.alternatives.rows || []).map(function (r) {
    var cls = r.sku_id === bestId ? " class='best'" : "";
    return "<tr" + cls + "><td>" + (r.row_type === "same_product" ? "同型号" : "跨型号") +
      "</td><td>" + esc(r.brand) + " " + esc(r.product_id) + " " + r.tier +
      "</td><td>" + r.channel + "</td><td>" + r.price + "</td><td>" +
      r.saving_pct.toFixed(1) + "%</td><td>" +
      (r.bench_ratio * 100).toFixed(0) + "%</td><td>" +
      (r.satisfies_need ? "是" : "否") + "</td></tr>";
  }).join("");
  return "<table><tr><th>关系</th><th>候选</th><th>渠道</th><th>现价</th><th>省/贵</th>" +
    "<th>性能比</th><th>满足用途</th></tr>" + rows + "</table>" +
    "<p class='muted'>[ref: alternatives + R03（每元性能与属性差异见 CLI/JSON 全字段）]</p>";
}
function evidenceHtml(card) {
  return (card.evidence || []).map(function (e, i) {
    return "<details><summary>" + i + ". [" + esc(e.ref) + "]</summary><p>" + esc(e.note) + "</p></details>";
  }).join("");
}
function editorHtml(profile) {
  var opts = {
    deadline: [["none", "不着急，能等到好价"], ["within_30", "一个月内"], ["within_90", "三个月内"], ["now", "必须马上有"]],
    usage_intensity: [["rarely", "偶尔"], ["low", "每周 1-3 次"], ["medium", "每周 3-10h"], ["high", "重度每天用"]],
    hedonic: [["utilitarian", "需要（影响正事）"], ["hedonic", "想要（升级体验）"]],
    wait_tier: [["low", "贴现高·难等"], ["mid", "一般"], ["high", "贴现低·能等"]],
    budget_tier: [["low", "入门就够"], ["mid", "主流中档"], ["high", "旗舰顶配"], ["flexible", "看性价比"]],
    price_view: [["up", "感觉要涨"], ["stable", "平稳"], ["down", "会降"], ["uncertain", "说不准"]],
    supply_news: [["no", "缺货消息少"], ["yes", "缺货/涨价消息多"]],
    alt_acceptable: [["no", "只接受全新同款"], ["yes", "可接受二手/平替"]]
  };
  var out = '<div class="editor-grid">';
  Object.keys(opts).forEach(function (k) {
    var cur = profile[k] != null ? profile[k] : opts[k][0][0];
    out += "<label>" + k + "<select id='ed-" + k + "'>" +
      opts[k].map(function (o) {
        return "<option value='" + o[0] + "'" + (o[0] === cur ? " selected" : "") + ">" + o[1] + "</option>";
      }).join("") + "</select></label>";
  });
  out += "</div>";
  var purp = profile.purpose || "游戏";
  out += '<p><label>用途 <select id="ed-purpose">' +
    ["游戏", "AI / 跑模型", "3D / 视频创作", "编程 / 日常", "其他"].map(function (p) {
      return "<option" + (p === purp ? " selected" : "") + ">" + p + "</option>";
    }).join("") + '</select></label> ' +
    '<button id="btn-recalc">按新参数重算</button> ' +
    '<button id="btn-reset" class="ghost">重置为问卷原答案</button></p>';
  return out;
}
function historyHtml(hist) {
  if (!hist || !hist.length) { return "<p class='muted'>暂无重算记录</p>"; }
  return hist.slice().reverse().map(function (h) {
    var o = Object.keys(h.overrides || {}).map(function (k) {
      return k + "=" + h.overrides[k];
    }).join("，");
    return "<div class='cond'><b>" + esc(h.at) + "</b>　改：" +
      esc(o || "（无）") + "　→　" + h.recommendation + " / " + LIGHT[h.traffic_light] +
      " / P2=" + pct1(h.p2) + "</div>";
  }).join("");
}
function detailsBox() { return ""; }
function cardTabHtml(id, label, on) {
  return "<button class='card-tab" + (on ? " on" : "") + "' id='ctab-" + id + "'>" + label + "</button>";
}
function profileRowsHtml(profile) {
  var labels = { flow: "流程", necessity: "必需性", purpose: "用途",
    deadline: "最晚需要", usage_intensity: "使用频率", budget_tier: "预算档",
    alt_acceptable: "二手/平替", hedonic: "想要/需要", wait_tier: "等待贴现档",
    price_view: "价格预期", supply_news: "缺货消息" };
  var vals = { deadline: { none: "不着急", within_30: "一月内", within_90: "三月内", now: "马上" },
    usage_intensity: { rarely: "偶尔", low: "每周1-3次", medium: "每周3-10h", high: "重度每天用" },
    budget_tier: { low: "入门档", mid: "中档", high: "旗舰档", flexible: "看性价比" },
    alt_acceptable: { yes: "可接受", no: "只接受全新" },
    hedonic: { utilitarian: "需要", hedonic: "想要" },
    wait_tier: { low: "难等（贴现高）", mid: "一般", high: "能等（贴现低）" },
    price_view: { up: "看涨", stable: "平稳", down: "看跌", uncertain: "说不准" },
    supply_news: { yes: "消息多", no: "消息少" },
    necessity: { essential: "必需", optional: "可选" },
    flow: { essential: "必需闸门", optional: "时机问卷" } };
  var rows = [];
  Object.keys(labels).forEach(function (k) {
    var v = profile[k];
    if (v == null) { return; }
    if (vals[k] && vals[k][v]) { v = vals[k][v]; }
    rows.push("<tr><th style='width:120px'>" + labels[k] +
      "</th><td style='text-align:left'>" + esc(String(v)) + "</td></tr>");
  });
  return rows.length ? "<table>" + rows.join("") + "</table>"
                     : "<p class='muted'>（无画像参数）</p>";
}
function setHint(msg) {
  var h = $("hint-status");
  if (h) { h.textContent = msg; }
}
function userBarHtml() {
  var status = "<span id='hint-status' class='muted2'></span>";
  if (!S.user && !S.snap) {
    return "<div class='user-toolbar'><span class='muted2'>游客模式：</span>" +
      "<button id='btn-hint-login' class='small'>登录 / 注册（出卡自动存档 + 关注）</button>" +
      status + "</div>";
  }
  var parts = [];
  if (S.snap) {
    parts.push("<button id='btn-rerun' class='small'>用这份画像重新出卡 →</button>");
    parts.push("<span class='muted2'>历史快照 · " + esc(S.snap.at) + "</span>");
  } else if (S.user) {
    parts.push("<span class='muted2'>已登录：出卡自动存档到「我的数据」</span>");
  }
  if (S.user && S.sku_id) {
    parts.push("<button id='btn-watch' class='small'>关注该商品</button>");
  }
  if (S.user && S.session_id && (S.savedState === "anon" || S.dirty)) {
    parts.push("<button id='btn-save-ver' class='small'>" +
      (S.dirty ? "把当前参数版本另存为一条历史" : "把这张决策卡存入我的历史") + "</button>");
  }
  if (!parts.length) { return ""; }
  return "<div class='user-toolbar'>" + parts.join(" ") + status + "</div>";
}
function renderCard(card, profile, hist, keepEditorOpen, snap) {
  var d = card.decision;
  var pl = d.plain_language || null;
  var plainHtml = (pl && pl.text)
    ? "<div class='cond plain'><b>大白话：</b>" + esc(pl.text) + "</div>" : "";
  var hints = card.behavior_hints || [];
  var hintsHtml = hints.length
    ? "<div class='bhints'>" + hints.map(function (h) {
        return "<div class='bhint'><b>" + esc(h.rule) + "</b>" + esc(h.text) +
          "<span class='bhint-ref'>" + esc(h.ref) + "</span></div>";
      }).join("") + "</div>"
    : "";
  var p2 = d.p2 || {};
  var why1 = "<p class='tip'>P1 是「历史考卷」：把过去翻出来看——价格处在现在这个" +
    "水平时，未来 30 / 60 / 180 天里降价 ≥5% 各出现过多少次，就是多大概率。" +
    "这个数越大，说明这个位置「再等等」更常见。</p>";
  var why2 = "<p class='tip'>P2 是「按你的情况模拟」：把急不急用、用得多频繁、" +
    "能等多久、涨价消息都当作变量做组合推演，在所有可能情况里'现在买'仍然是最" +
    "优的概率。P1 只讲价格历史，P2 把你个人的账也算进去了。</p>";
  var p2note = "<p class='muted'>P2 口径：概率 ≈ " + pct1(p2.probability) +
    "，共 " + (p2.n_scenarios || "-") + " 组情景扰动（档位/期限/波动率/通胀预期/供需）</p>";
  var snapNote = snap
    ? "<div class='cond'><b>历史快照</b>　保存于 " + esc(snap.at || "") +
      "。以下为当时的完整结论，可随时回来查看；要带新参数重算请用上方按钮。</div>"
    : "";// 概率详解 tab
  var tabProb = why1 + p1Table(card) + why2 + p2note + decompTable(card);
  // 条件与事件 tab
  var tabCond = conditionsHtml(card) + eventsHtml(card) + altTable(card);
  // 假设与依据 tab（含假设编辑器与依据链）
  var tabAssump = snap
    ? "<p class='tip'>点上方「用这份画像重新出卡」会回到问答流程，同品类历史答案自动预填。"
    : editorHtml(profile);
  var tabRefer = evidenceHtml(card);
  var histBox = snap ? "" : "<h4>重算记录</h4><div id='hist-box'>" + historyHtml(hist) + "</div>";

  return "<div class='ui-panel'>" + banner(card) + plainHtml + hintsHtml + snapNote +
    userBarHtml() + "</div>" +
    "<div class='ui-panel'><h3>K 线与价格统计 <span class='badge'>合成数据</span></h3>" +
    "<div id='kline-box'></div>" + kpiRow(card) +
    "<p class='muted'>周线（自绘 SVG，离线可用）｜现价 " + card.stats.last_price +
    " 元（" + card.stats.asof + "）｜MA20 " + (card.stats.ma["20"] || "-") +
    "｜MA60 " + (card.stats.ma["60"] || "-") + "｜90 天波动率分位 " +
    ((card.stats.volatility.pct_position || 0) * 100).toFixed(0) + "%</p>" +
    "<p class='hint'>想看懂每个数字怎么来的？点下方小标题逐层展开 ↓</p>" +
    "<div class='card-tabs'>" +
      cardTabHtml("prob", "概率详解", true) +
      cardTabHtml("cond", "条件与事件", false) +
      cardTabHtml("assump", "假设与依据", false) +
    "</div>" +
    "<div class='card-pane' id='cpane-prob'>" + tabProb + "</div>" +
    "<div class='card-pane hidden' id='cpane-cond'>" + tabCond + "</div>" +
    "<div class='card-pane hidden' id='cpane-assump'>" + tabAssump + histBox + "</div>" +
    "</div>" +
    "<div class='ui-panel'><h3>依据链（口径 / 样本 / 假设）</h3>" + tabRefer + "</div>";
}
function refreshWatchState() {
  if (!S.user || !S.sku_id) { return; }
  api("GET", "/api/me/watchlist").then(function (j) {
    S.watchMap = {};
    (j.watchlist || []).forEach(function (w) { S.watchMap[w.sku_id] = true; });
    var b = $("btn-watch");
    if (b) {
      b.textContent = S.watchMap[S.sku_id] ? "已关注 ✓（点击取消）" : "关注该商品";
    }
  }).catch(function () {});
}
function toggleWatch() {
  var sku = S.sku_id;
  if (!sku || !S.user) { return; }
  var on = !!S.watchMap[sku];
  var req = on
    ? api("DELETE", "/api/me/watchlist?sku_id=" + encodeURIComponent(sku))
    : api("PUT", "/api/me/watchlist", { sku_id: sku });
  var b = $("btn-watch");
  if (b) { b.disabled = true; }
  req.then(function () {
    S.watchMap[sku] = !on;
    var nb = $("btn-watch");
    if (nb) { nb.textContent = !on ? "已关注 ✓（点击取消）" : "关注该商品"; }
    setHint(!on ? "已关注，可在「我的数据 → 关注商品」随时找回重新出卡。" : "已取消关注。");
  }).catch(function (e) { setHint("操作失败：" + e.message); })
    .then(function () { if (b) { b.disabled = false; } });
}
function saveCurrentVersion() {
  if (!S.session_id || !S.user) { return; }
  var b = $("btn-save-ver");
  if (b) { b.disabled = true; }
  api("POST", "/api/me/cards", { session_id: S.session_id }).then(function () {
    S.dirty = false; S.savedState = "manual";
    setHint("已另存一条历史，见「我的数据 → 决策历史」。");
    var nb = $("btn-save-ver");
    if (nb) { nb.classList.add("hidden"); }
  }).catch(function (e) { setHint("保存失败：" + e.message); })
    .then(function () { if (b) { b.disabled = false; } });
}
function bindCardEvents(card) {
  var kbox = $("kline-box");
  if (kbox) {
    fetch("/api/kline?sku_id=" + encodeURIComponent(card.meta.sku_id))
      .then(function (r) { return r.text(); })
      .then(function (svg) { kbox.innerHTML = svg; })
      .catch(function () { kbox.innerHTML = "<p class='tip'>K 线加载失败</p>"; });
  }
  // 决策卡 tab 切换
  ["prob", "cond", "assump"].forEach(function (id) {
    var t = $("ctab-" + id);
    if (t) {
      t.onclick = function () {
        document.querySelectorAll(".card-tab").forEach(function (x) { x.classList.toggle("on", x === t); });
        ["prob", "cond", "assump"].forEach(function (pid) {
          var p = $("cpane-" + pid);
          if (p) { p.classList.toggle("hidden", pid !== id); }
        });
      };
    }
  });
  var b = $("btn-recalc");
  if (b) {
    b.onclick = function () {
      var over = {};
      ["deadline", "usage_intensity", "hedonic", "wait_tier", "budget_tier",
       "price_view", "supply_news", "alt_acceptable"].forEach(function (k) {
        var el = $("ed-" + k);
        if (el) { over[k] = el.value; }
      });
      var p = $("ed-purpose");
      if (p) { over.purpose = p.value; }
      b.disabled = true;
      api("POST", "/api/recompute", { session_id: S.session_id, overrides: over })
        .then(function (j) {
          S.profile = j.profile; S.card = j.card; S.hist = j.history || [];
          S.dirty = true;
          $("card-root").innerHTML = renderCard(j.card, j.profile, S.hist, true, null);
          bindCardEvents(j.card);
          var hb = $("hist-box");
          if (hb) { hb.scrollIntoView({ behavior: "smooth", block: "nearest" }); }
        }).catch(function (e) { alert("重算失败：" + e.message); })
        .then(function () { b.disabled = false; });
    };
  }
  var r = $("btn-reset");
  if (r) {
    r.onclick = function () {
      api("POST", "/api/recompute", { session_id: S.session_id, overrides: {} })
        .then(function (j) {
          S.profile = j.profile; S.card = j.card; S.hist = j.history || [];
          S.dirty = true;
          $("card-root").innerHTML = renderCard(j.card, j.profile, S.hist, true, null);
          bindCardEvents(j.card);
        }).catch(function (e) { alert("重置失败：" + e.message); });
    };
  }
  var w = $("btn-watch");
  if (w) { w.onclick = function () { toggleWatch(); }; }
  var sv = $("btn-save-ver");
  if (sv) { sv.onclick = function () { saveCurrentVersion(); }; }
  var lg = $("btn-hint-login");
  if (lg) { lg.onclick = function () { openAuth("login"); }; }
  var rn = $("btn-rerun");
  if (rn) { rn.onclick = function () { if (S.product) { startRerun(S.product); } }; }
  if (w || sv) { refreshWatchState(); }
}

/* ---------- 我的数据（历史 / 关注 / 账号） ---------- */
var ME = { tab: "history" };
function openMe() {
  S.afterAuth = null;
  setNav("view-me");
  meTab("history");
}
function meTab(name) {
  ME.tab = name;
  var tabs = [["tab-history", "history"], ["tab-watch", "watch"], ["tab-account", "account"]];
  tabs.forEach(function (t) { $(t[0]).classList.toggle("on", t[1] === name); });
  if (name === "history") { renderHistory(); }
  else if (name === "watch") { renderWatch(); }
  else { renderAccount(); }
}
function kindTag(c) {
  if (c.kind !== "card") { return "<span class='tag gray'>无价格库 · 仅画像</span>"; }
  var cl = c.traffic_light === "green" ? "green"
         : c.traffic_light === "red" ? "red" : "yellow";
  return "<span class='tag " + cl + "'>" + esc(recTxt(c.recommendation)) + "</span>";
}
function historyItemHtml(c) {
  var name = (c.product && c.product.name) || "（未命名商品）";
  var cat = (c.product && c.product.category) || "";
  var extra = c.kind !== "card" && c.note ? "<br><span class='muted'>" + esc(c.note) + "</span>" : "";
  return "<li><div class='row-2'><div><b>" + esc(name) + "</b> " +
    "<span class='muted'>" + esc(cat) + "</span> " + kindTag(c) +
    "<br><span class='muted'>" + esc(c.at) + "</span>" + extra + "</div>" +
    "<div class='row small-row'>" +
    (c.kind === "card" ? "<button id='hv-" + c.id + "' class='ghost small'>查看完整卡</button> " : "") +
    "<button id='hr-" + c.id + "' class='ghost small'>重跑流程</button> " +
    "<button id='hd-" + c.id + "' class='ghost small danger'>删除</button>" +
    "</div></div></li>";
}
function bindHistoryItem(c) {
  var v = $("hv-" + c.id);
  if (v) { v.onclick = function () { openHistoryCard(c.id); }; }
  var r = $("hr-" + c.id);
  if (r) { r.onclick = function () { startRerun(c.product || {}); }; }
  var d = $("hd-" + c.id);
  if (d) { d.onclick = function () { delHistory(c.id); }; }
}
function delHistory(id) {
  if (!window.confirm("删除这条决策历史？")) { return; }
  api("DELETE", "/api/me/cards/" + id).then(function () { renderHistory(); })
    .catch(function (e) { alert("删除失败：" + e.message); });
}
function renderHistory() {
  var body = $("me-body");
  $("me-summary").textContent = "加载中…";
  body.innerHTML = "<p class='tip'>加载中…</p>";
  api("GET", "/api/me/cards").then(function (j) {
    var cards = j.cards || [];
    $("me-summary").textContent = S.user + " 的决策历史：共 " + cards.length +
      " 条（完整快照保存，可查看还原 / 重跑 / 删除）。";
    if (!cards.length) {
      body.innerHTML = "<p class='me-empty'>还没有决策记录。去首页贴个商品链接走一次问答，结果会自动存到这里。</p>";
      return;
    }
    body.innerHTML = "<ul class='me-list'>" + cards.map(historyItemHtml).join("") + "</ul>";
    cards.forEach(bindHistoryItem);
  }).catch(function (e) {
    if (isAuthErr(e)) { authExpired(); return; }
    body.innerHTML = "<p class='me-empty'>加载失败：" + esc(e.message) + "</p>";
  });
}
function openHistoryCard(cid) {
  api("GET", "/api/me/cards/" + cid).then(function (e) {
    if (!e) { throw new Error("记录不存在"); }
    S.product = e.product || {}; S.sku_id = e.sku_id || null;
    S.profile = e.profile || {}; S.hist = [];
    S.session_id = null; S.dirty = false; S.questions = [];
    S.savedState = "snap";
    if (e.kind === "card" && e.snapshot) {
      S.card = e.snapshot;
      S.snap = { at: e.at, id: e.id };
      showCard(e.snapshot);
    } else {
      S.card = null;
      S.snap = { at: e.at, id: e.id };
      $("no-data").classList.remove("hidden");
      show("view-card"); setStep(3);
      $("card-root").innerHTML = "";
      $("no-data").innerHTML =
        '<div class="panel"><h3>历史记录：流程结论（当时无该型号价格库）</h3>' +
        "<p>" + esc(e.note || "未出量化卡") + "</p>" +
        "<p class='muted'>保存时间 " + esc(e.at) + "</p>" +
        "<div class='cond'>" + profileRowsHtml(e.profile || {}) + "</div>" +
        '<p><button id="nd-run">重新跑一次 →</button> ' +
        '<button id="nd-back" class="ghost">返回我的数据</button></p></div>';
      $("nd-run").onclick = function () { startRerun(e.product || {}); };
      $("nd-back").onclick = function () { openMe(); };
    }
  }).catch(function (err) { alert("读取失败：" + err.message); });
}
function watchItemHtml(w) {
  return "<li><div class='row-2'><div><b>" + esc(w.name || w.sku_id) + "</b> " +
    "<span class='tag blue'>" + esc(w.brand || "") + " " + esc(w.tier || "") + "</span>" +
    "<br><span class='muted'>" + esc(w.sku_id) + " · 现价 ¥" + esc(String(w.price)) +
    " · 关注于 " + esc(w.at) + "</span></div>" +
    "<div class='row small-row'>" +
    "<button id='wr-" + esc(w.sku_id) + "' class='ghost small'>重新出卡</button> " +
    "<button id='wu-" + esc(w.sku_id) + "' class='ghost small danger'>取消关注</button>" +
    "</div></div></li>";
}
function bindWatchItem(w) {
  var r = $("wr-" + w.sku_id);
  if (r) { r.onclick = function () { startRerun({ name: w.name, category: w.category }); }; }
  var u = $("wu-" + w.sku_id);
  if (u) {
    u.onclick = function () {
      api("DELETE", "/api/me/watchlist?sku_id=" + encodeURIComponent(w.sku_id))
        .then(function () { renderWatch(); })
        .catch(function (e) { alert("取消失败：" + e.message); });
    };
  }
}
function renderWatch() {
  var body = $("me-body");
  $("me-summary").textContent = "加载中…";
  body.innerHTML = "<p class='tip'>加载中…</p>";
  api("GET", "/api/me/watchlist").then(function (j) {
    var list = j.watchlist || [];
    $("me-summary").textContent = S.user + " 关注了 " + list.length +
      " 个商品：关注只是替你记住它，等价格有变化或你想买时回来重新出卡。";
    if (!list.length) {
      body.innerHTML = "<p class='me-empty'>还没有关注商品。出卡后点卡片上的「关注该商品」就会出现在这里。</p>";
      return;
    }
    body.innerHTML = "<ul class='me-list'>" + list.map(watchItemHtml).join("") + "</ul>";
    list.forEach(bindWatchItem);
  }).catch(function (e) {
    if (isAuthErr(e)) { authExpired(); return; }
    body.innerHTML = "<p class='me-empty'>加载失败：" + esc(e.message) + "</p>";
  });
}
function exportData() {
  var t = token();
  fetch("/api/me/export", { headers: t ? { "X-Iris-Token": t } : {} })
    .then(function (r) {
      if (!r.ok) { throw new Error("HTTP " + r.status); }
      return r.blob();
    }).then(function (blob) {
      var a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "iris-export-" + (S.user || "user") + ".json";
      document.body.appendChild(a); a.click();
      setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 800);
    }).catch(function (e) { alert("导出失败：" + e.message); });
}
function deleteAccount() {
  if (!window.confirm("确定注销账号「" + S.user + "」？这会删除全部历史、关注与画像，不可恢复。")) { return; }
  if (!window.confirm("再确认一次：真的要永久删除全部数据吗？")) { return; }
  api("DELETE", "/api/me").then(function () {
    forgetUser(); refreshUserBar();
    show("view-input"); setStep(1);
    $("resolve-out").innerHTML = '<p class="tip">账号已注销，本机全部数据已删除。</p>';
  }).catch(function (e) { alert("注销失败：" + e.message); });
}
function renderAccount() {
  var body = $("me-body");
  $("me-summary").textContent = "加载中…";
  body.innerHTML = "<p class='tip'>加载中…</p>";
  api("GET", "/api/me").then(function (m) {
    var st = m.stats || {};
    $("me-summary").textContent = "账号与数据只保存在本机 data/users/，可导出备份或注销删除。";
    body.innerHTML =
      '<div class="panel"><table>' +
      "<tr><th style='width:120px'>用户名</th><td style='text-align:left'>" + esc(m.username) + "</td></tr>" +
      "<tr><th>注册时间</th><td style='text-align:left'>" + esc(m.created_at) + "</td></tr>" +
      "<tr><th>决策历史</th><td style='text-align:left'>" + st.cards + " 条</td></tr>" +
      "<tr><th>关注商品</th><td style='text-align:left'>" + st.watch + " 个</td></tr>" +
      "<tr><th>画像档案</th><td style='text-align:left'>" + st.profiles + " 个品类</td></tr>" +
      "</table></div>" +
      '<div class="panel"><h4>数据操作</h4>' +
      "<p><button id='btn-export' class='ghost'>导出我的数据（JSON）</button> " +
      "<button id='btn-del-user' class='ghost danger'>注销账号并删除全部数据</button></p>" +
      "<p class='muted'>导出包含完整决策卡快照、关注清单与分品类画像答案。注销不可恢复。</p></div>" +
      "<p class='me-note'>密码以 PBKDF2（SHA-256 · 20 万轮 · 随机盐）哈希存储，本机不落明文；" +
      "登录令牌保存在浏览器 localStorage（7 天过期，服务重启后需重新登录）。</p>";
    $("btn-export").onclick = exportData;
    $("btn-del-user").onclick = deleteAccount;
  }).catch(function (e) {
    if (isAuthErr(e)) { authExpired(); return; }
    body.innerHTML = "<p class='me-empty'>加载失败：" + esc(e.message) + "</p>";
  });
}

/* ---------- 初始化 ---------- */
document.addEventListener("DOMContentLoaded", function () {
  $("btn-resolve").onclick = function () { resolveText($("text").value); };
  $("btn-prev").onclick = prevQ;
  chipFill();
  $("btn-login").onclick = function () { openAuth("login"); };
  $("btn-logout").onclick = doLogout;
  var sbNav = $("sb-nav");
  if (sbNav) {
    document.querySelectorAll(".sbtn[data-view]").forEach(function (b) {
      var v = b.getAttribute("data-view");
      b.onclick = function () {
        if (v === "me") { openMe(); }
        else {
          document.querySelectorAll(".sbtn[data-view]").forEach(function (x) { x.classList.toggle("on", x === b); });
          $("view-me").classList.add("hidden");
          $("flow-root").classList.remove("hidden");
          show(LAST_MAIN || "view-input");
          if (LAST_MAIN === "view-questions") { setStep(2); }
          else if (LAST_MAIN === "view-card") { setStep(3); }
          else { setStep(1); }
        }
      };
    });
  }
  $("btn-auth-go").onclick = doAuth;
  $("btn-auth-toggle").onclick = function () {
    AUTH.mode = AUTH.mode === "register" ? "login" : "register";
    authLabels(); $("auth-err").textContent = "";
  };
  $("btn-auth-back").onclick = function () {
    S.afterAuth = null;
    closeAuth();
  };
  var authModal = $("auth-modal");
  if (authModal) {
    authModal.querySelector(".modal-backdrop").onclick = closeAuth;
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !$("auth-modal").classList.contains("hidden")) { closeAuth(); }
      if (e.key === "Enter" && !$("auth-modal").classList.contains("hidden")) { doAuth(); }
    });
  };
  $("btn-me-back").onclick = function () {
    var back = LAST_MAIN === "view-me" ? "view-input" : (LAST_MAIN || "view-input");
    show(back);
    if (back === "view-questions") { setStep(2); }
    else if (back === "view-card") { setStep(3); }
    else { setStep(1); }
  };
  $("tab-history").onclick = function () { meTab("history"); };
  $("tab-watch").onclick = function () { meTab("watch"); };
  $("tab-account").onclick = function () { meTab("account"); };
  initSession();
});

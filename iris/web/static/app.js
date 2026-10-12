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
function updateDialNav(pane) {
  var menu = $("dial-items");
  var h = $("dial-item-history");
  var s = $("dial-item-showcase");
  var a = $("dial-item-auth");

  var rotMap = {
    "pane-history": "24deg",
    "pane-showcase": "0deg",
    "pane-questions": "0deg",
    "pane-card": "0deg",
    "pane-auth": "-24deg"
  };

  if (menu) {
    menu.style.setProperty("--dial-rot", rotMap[pane] || "0deg");
  }

  if (h) h.classList.toggle("active", pane === "pane-history");
  if (s) s.classList.toggle("active", pane === "pane-showcase" || pane === "pane-questions" || pane === "pane-card");
  if (a) a.classList.toggle("active", pane === "pane-auth");
}

function show(id) {
  var idMap = {
    "view-input": "pane-showcase",
    "view-questions": "pane-questions",
    "view-card": "pane-card",
    "view-me": "pane-history",
    "pane-showcase": "pane-showcase",
    "pane-history": "pane-history",
    "pane-auth": "pane-auth",
    "pane-questions": "pane-questions",
    "pane-card": "pane-card"
  };
  var targetPane = idMap[id] || id;
  ["pane-showcase", "pane-history", "pane-auth", "pane-questions", "pane-card"].forEach(function (p) {
    var el = $(p);
    if (el) { el.classList.toggle("hidden", p !== targetPane); }
  });
  if (targetPane === "pane-showcase" || targetPane === "pane-questions" || targetPane === "pane-card") {
    LAST_MAIN = targetPane;
  }
  updateDialNav(targetPane);
  window.scrollTo(0, 0);
}
function setStep(i) {
  ["step-i", "step-q", "step-c"].forEach(function (s, k) {
    var el = $(s);
    if (el) el.classList.toggle("on", k < i);
  });
}
function setNav(view) {
  updateDialNav(view === "view-me" ? "pane-history" : "pane-showcase");
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
  var unameEl = $("sb-ub-name");
  if (unameEl) {
    unameEl.textContent = S.user || "";
    unameEl.classList.toggle("hidden", !on);
  }
  var loggedInBox = $("auth-logged-in");
  var loggedOutBox = $("auth-logged-out");
  var curUserDisplay = $("current-user-display");
  if (loggedInBox && loggedOutBox) {
    loggedInBox.classList.toggle("hidden", !on);
    loggedOutBox.classList.toggle("hidden", on);
    if (curUserDisplay) curUserDisplay.textContent = S.user || "";
  }
}
function authExpired() {
  forgetUser(); refreshUserBar();
  show("view-input"); setStep(1); setNav("view-input");
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
  }).catch(function () { forgetUser(); refreshUserBar(); setNav("view-input"); });
}

/* ---------- 登录 / 注册 视图 ---------- */
var AUTH = { mode: "login" };
function authLabels() {
  var reg = AUTH.mode === "register";
  $("auth-title").textContent = reg ? "创建账号" : "欢迎回来";
  $("auth-sub").textContent = reg
    ? "30 秒完成注册，决策记录开始自动存档。"
    : "输入账号密码，继续你的决策记录。";
  $("auth-user-hint").textContent = reg ? "2-20 位中文 / 字母 / 数字 / 下划线" : "你注册时填的用户名";
  $("auth-pass-hint").textContent = reg ? "至少 6 位，建议字母 + 数字组合" : "至少 6 位";
  $("btn-auth-go").textContent = reg ? "创建账号" : "登录";
  $("auth-benefit-title").textContent = reg ? "注册即获得" : "登录后能得到";
  var items = reg
    ? [["历史自动存档", "从第一张决策卡开始记录，不用手动保存"],
       ["画像免重填", "下次同品类问卷自动预填，直接出卡"],
       ["关注商品", "收藏查过的 SKU，随时回来重新决策"]]
    : [["历史自动存档", "每次决策卡完整快照，一键还原回看"],
       ["画像免重填", "同品类问卷自动预填，直接沿用出卡"],
       ["关注商品", "收藏查过的 SKU，随时回来重新出卡"]];
  $("auth-benefit-list").innerHTML = items.map(function (it) {
    return "<li><b>" + esc(it[0]) + "</b> — " + esc(it[1]) + "</li>";
  }).join("");
  $("atab-login").classList.toggle("on", !reg);
  $("atab-login").setAttribute("aria-selected", !reg ? "true" : "false");
  $("atab-register").classList.toggle("on", reg);
  $("atab-register").setAttribute("aria-selected", reg ? "true" : "false");
  $("auth-card").classList.toggle("mode-register", reg);
  var passInput = $("auth-pass");
  passInput.setAttribute("autocomplete", reg ? "new-password" : "current-password");
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
  var qc = $("q-count");
  if (qc) { qc.textContent = (Q.idx + 1) + " / " + Q.items.length; }
  var qf = $("q-fill");
  if (qf) { qf.style.width = Math.round((Q.idx + 1) / Q.items.length * 100) + "%"; }
  $("q-body").innerHTML =
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
  var p1Prob = card.p1 && card.p1["60"] && card.p1["60"].probability != null ? card.p1["60"].probability : 0;
  var p1N = card.p1 && card.p1["60"] ? card.p1["60"].n : 0;
  var p2Prob = d.p2 && d.p2.probability != null ? d.p2.probability : 0;
  var st = card.stats || {};
  var lastPrice = st.last_price != null ? "¥" + st.last_price : "";
  var prodName = (card.meta && card.meta.brand ? card.meta.brand.toUpperCase() + " " : "") +
                 (card.meta && card.meta.product_id ? card.meta.product_id.toUpperCase() : "");

  var circ = 213.6;
  var p1Offset = (circ * (1 - Math.min(1, Math.max(0, p1Prob)))).toFixed(1);
  var p2Offset = (circ * (1 - Math.min(1, Math.max(0, p2Prob)))).toFixed(1);

  var statusTitle = d.recommendation === "switch" ? "VALUE ARBITRAGE · 换款平替最优"
                  : d.recommendation === "buy" ? "OPTIMAL TIMING · 建议现在买入"
                  : "TIMING BUFFER · 建议观望等待";

  var headline = d.recommendation === "switch" ? "当前款高位溢价，平替方案性价比极高"
               : d.recommendation === "buy" ? "价格处于安全边际，买入综合效用最高"
               : "短期降价概率显著，建议设阈等待击穿";

  return '<div class="dossier-hero ' + k + '">' +
    '<div class="dossier-hero-main">' +
      '<div class="dossier-badge-row">' +
        '<span class="dossier-status-pill ' + k + '"><span class="pulse-dot"></span> ' + statusTitle + '</span>' +
        (prodName ? '<span class="dossier-meta-chip">' + esc(prodName) + (lastPrice ? ' · ' + lastPrice : '') + '</span>' : '') +
      '</div>' +
      '<h1 class="dossier-headline">' + recTxt0 + ' <span class="dossier-light-tag">' + LIGHT[d.traffic_light] + '</span></h1>' +
      '<p class="dossier-subhead">' + headline + '</p>' +
    '</div>' +
    '<div class="dossier-hero-meters">' +
      '<div class="meter-box">' +
        '<div class="svg-radial-wrap">' +
          '<svg width="76" height="76" viewBox="0 0 76 76">' +
            '<circle cx="38" cy="38" r="34" class="meter-bg" />' +
            '<circle cx="38" cy="38" r="34" class="meter-fill" style="stroke-dasharray:' + circ + ';stroke-dashoffset:' + p1Offset + ';" />' +
          '</svg>' +
          '<span class="meter-center-text">' + pct1(p1Prob) + '</span>' +
        '</div>' +
        '<div class="meter-info"><div class="meter-title">P1 降价概率</div><div class="meter-sub">60天降≥5% (n=' + p1N + ')</div></div>' +
      '</div>' +
      '<div class="meter-box">' +
        '<div class="svg-radial-wrap">' +
          '<svg width="76" height="76" viewBox="0 0 76 76">' +
            '<circle cx="38" cy="38" r="34" class="meter-bg" />' +
            '<circle cx="38" cy="38" r="34" class="meter-fill" style="stroke-dasharray:' + circ + ';stroke-dashoffset:' + p2Offset + ';" />' +
          '</svg>' +
          '<span class="meter-center-text">' + pct1(p2Prob) + '</span>' +
        '</div>' +
        '<div class="meter-info"><div class="meter-title">P2 决策胜率</div><div class="meter-sub">60天内最优买入</div></div>' +
      '</div>' +
    '</div>' +
  '</div>';
}

function arbitrageCardHtml(card, profile) {
  var d = card.decision;
  var sw = d.switch_to;
  if (!sw && d.recommendation !== "switch") { return ""; }
  var st = card.stats || {};
  var origPrice = st.last_price || (sw ? sw.price + sw.saving_yuan : 0);
  var origName = (card.meta && card.meta.brand ? card.meta.brand.toUpperCase() + " " : "") +
                 (card.meta && card.meta.product_id ? card.meta.product_id.toUpperCase() : "原选定型号");
  var altName = (sw ? sw.brand.toUpperCase() + " " + sw.product_id.toUpperCase() + " " + (sw.tier || "") : "推荐高性价比平替");
  var altPrice = sw ? sw.price : 0;
  var saveYuan = sw ? sw.saving_yuan : (origPrice - altPrice);
  var savePct = sw ? sw.saving_pct : (saveYuan / (origPrice || 1) * 100);
  var benchPct = sw ? Math.round(sw.bench_ratio * 100) : 85;
  var purp = (profile && profile.purpose) || "日常/综合用途";

  return '<div class="arbitrage-card">' +
    '<div class="arb-header">' +
      '<div class="arb-title-group">' +
        '<span class="arb-badge">VALUE ARBITRAGE · 决策平替对冲方案</span>' +
        '<h3 class="arb-title">换一个买更划算：性能达 ' + benchPct + '%，直省 ¥' + saveYuan + ' (' + savePct.toFixed(1) + '%)</h3>' +
      '</div>' +
      '<div class="arb-tag-save">-¥' + saveYuan + '</div>' +
    '</div>' +
    '<div class="arb-comparison-grid">' +
      '<div class="arb-col">' +
        '<div class="arb-col-header"><span class="arb-col-label">原评估目标</span><span class="arb-col-price">¥' + origPrice + '</span></div>' +
        '<div class="arb-col-name">' + esc(origName) + '</div>' +
        '<div class="arb-bar-row">' +
          '<span class="arb-bar-desc">性能基准 Benchmark</span>' +
          '<div class="arb-track"><div class="arb-fill" style="width:100%;"></div></div>' +
          '<span class="arb-bar-pct">100%</span>' +
        '</div>' +
      '</div>' +
      '<div class="arb-vs-badge">VS</div>' +
      '<div class="arb-col highlight">' +
        '<div class="arb-col-header"><span class="arb-col-label highlight">推荐高性价比平替</span><span class="arb-col-price highlight">¥' + altPrice + '</span></div>' +
        '<div class="arb-col-name highlight">' + esc(altName) + '</div>' +
        '<div class="arb-bar-row">' +
          '<span class="arb-bar-desc">满足【' + esc(purp) + '】用途</span>' +
          '<div class="arb-track"><div class="arb-fill highlight" style="width:' + benchPct + '%;"></div></div>' +
          '<span class="arb-bar-pct highlight">' + benchPct + '%</span>' +
        '</div>' +
      '</div>' +
    '</div>' +
    '<div class="arb-footer-note">' +
      '<b>量化裁决：</b>满足您的【' + esc(purp) + '】用途，原目标存在约 ' + savePct.toFixed(1) + '% 的旗舰/散热溢价。若非追求极限跑分，选择此平替可立即节约 ¥' + saveYuan + '。' +
    '</div>' +
  '</div>';
}

function priceSpectrumHtml(card) {
  var st = card.stats || {}, lb = st.lookbacks || {};
  var cb = st.conformal_bounds || {};
  var mr = st.mean_reversion || {};
  var last = st.last_price || 0;
  if (!last) { return ""; }

  var lb90 = lb["90"] || {};
  var minP = lb90.min || (cb.lower_bound ? Math.round(cb.lower_bound * 0.92) : Math.round(last * 0.8));
  var maxP = lb90.max || (cb.upper_bound ? Math.round(cb.upper_bound * 1.08) : Math.round(last * 1.2));
  var span = Math.max(1, maxP - minP);

  var curPos = Math.max(3, Math.min(97, (last - minP) / span * 100)).toFixed(1);
  var cbLeft = cb.lower_bound ? Math.max(0, (cb.lower_bound - minP) / span * 100).toFixed(1) : "0";
  var cbWidth = (cb.lower_bound && cb.upper_bound) ? Math.min(100 - parseFloat(cbLeft), (cb.upper_bound - cb.lower_bound) / span * 100).toFixed(1) : "0";
  var mrPos = mr.equilibrium_price ? Math.max(3, Math.min(97, (mr.equilibrium_price - minP) / span * 100)).toFixed(1) : null;

  var bandHtml = (cb.lower_bound && cb.upper_bound)
    ? '<div class="spectrum-band" style="left:' + cbLeft + '%;width:' + cbWidth + '%;" title="共形预测带: ¥' + cb.lower_bound + '~¥' + cb.upper_bound + '"></div>' : '';

  var mrHtml = mrPos
    ? '<div class="spectrum-marker mr-marker" style="left:' + mrPos + '%;" title="OU长期中枢: ¥' + mr.equilibrium_price + '"><div class="marker-line"></div><span class="marker-tag">中枢 ¥' + mr.equilibrium_price + '</span></div>' : '';

  return '<div class="spectrum-card">' +
    '<div class="spectrum-header">' +
      '<div class="spectrum-title"><span class="spectrum-pill">PRICE SPECTRUM</span> 价格空间与共形置信区间</div>' +
      '<div class="spectrum-legend">' +
        '<span class="legend-item"><span class="legend-swatch band-swatch"></span> 90% 置信带</span>' +
        '<span class="legend-item"><span class="legend-swatch cur-swatch"></span> 现价 ¥' + last + '</span>' +
        (mrPos ? '<span class="legend-item"><span class="legend-swatch mr-swatch"></span> OU 中枢 ¥' + mr.equilibrium_price + '</span>' : '') +
      '</div>' +
    '</div>' +
    '<div class="spectrum-bar-wrap">' +
      '<div class="spectrum-track">' +
        bandHtml +
        mrHtml +
        '<div class="spectrum-pin" style="left:' + curPos + '%;">' +
          '<div class="pin-glow"></div>' +
          '<div class="pin-badge">¥' + last + '</div>' +
        '</div>' +
      '</div>' +
      '<div class="spectrum-axis">' +
        '<span>¥' + Math.round(minP) + ' (90D 低)</span>' +
        '<span>¥' + Math.round(maxP) + ' (90D 高)</span>' +
      '</div>' +
    '</div>' +
  '</div>';
}

function chartCardHtml(card) {
  return '<div class="chart-card">' +
    '<div class="chart-header">' +
      '<div class="chart-title-wrap">' +
        '<span class="chart-pill">MARKET TRAJECTORY</span>' +
        '<h3 class="chart-heading">真实周 K 线走势与波动通道</h3>' +
      '</div>' +
      '<div class="chart-meta">7D 周频 · 真实市场归档序列</div>' +
    '</div>' +
    '<div id="kline-box" class="kline-viewport"><div class="chart-loading">加载价格周线图...</div></div>' +
  '</div>';
}

function behavioralGridHtml(card) {
  var pp = card.decision && card.decision.price_protection;
  var hints = card.behavior_hints || [];
  var cpu = null, fresh = null;
  hints.forEach(function (h) {
    if (h.rule === "cost_per_use_nudge") { cpu = h; }
    if (h.rule === "fresh_card") { fresh = h; }
  });

  var ppCard = pp ? (
    '<div class="b-card">' +
      '<div class="b-badge-row"><span class="b-badge cyan">HOPPER OPTION</span><span class="b-sub">30天回望看跌期权</span></div>' +
      '<div class="b-val">¥' + pp.fair_premium_yuan + '</div>' +
      '<div class="b-desc">期望下行 <b>' + pp.expected_drop_pct + '%</b>，30天降价概率 <b>' + (pp.drop_probability * 100).toFixed(0) + '%</b>。</div>' +
      '<div class="b-note">' + esc(pp.arbitrage_advice) + '</div>' +
    '</div>'
  ) : '';

  var cpuCard = cpu ? (
    '<div class="b-card">' +
      '<div class="b-badge-row"><span class="b-badge amber">COST PER USE</span><span class="b-sub">单次使用折旧精算</span></div>' +
      '<div class="b-val">折旧评估</div>' +
      '<div class="b-note">' + esc(cpu.text) + '</div>' +
    '</div>'
  ) : '';

  var freshCard = fresh ? (
    '<div class="b-card">' +
      '<div class="b-badge-row"><span class="b-badge bone">COOLING PERIOD</span><span class="b-sub">冲动消费阻断</span></div>' +
      '<div class="b-val">24H 冷却</div>' +
      '<div class="b-note">' + esc(fresh.text) + '</div>' +
    '</div>'
  ) : '';

  if (!ppCard && !cpuCard && !freshCard) { return ""; }
  return '<div class="behavioral-grid">' + ppCard + cpuCard + freshCard + '</div>';
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
  var sa = card.p1 && card.p1["60"] && card.p1["60"].survival_analysis;
  var saHtml = "";
  if (sa && sa.median_days_to_drop) {
    var iqrStr = sa.iqr_days ? "（50% 集中在 " + sa.iqr_days[0] + " ~ " + sa.iqr_days[1] + " 天）" : "";
    saHtml = "<div class='cond' style='margin-top:8px;'><b>降价生存期（Kaplan-Meier 时间分析）：</b>" +
      "历史同分位降价事件中，中位等待时长约为 <b>" + sa.median_days_to_drop + " 天</b>" + iqrStr + "。</div>";
  }
  return "<table><tr><th>窗口</th><th>P1 概率</th><th>95% CI</th><th>样本 n</th><th>方向</th></tr>" +
    rows + "</table>" + saHtml + "<p class='muted'>[ref: p1.windows + R04 校准口径；同分位段历史频率与生存期]</p>";
}
function decompTable(card) {
  var d = card.decision, c = d.decomposition;
  if (!c) { return ""; }
  var strikeRow = "";
  if (c.strike_price && c.net_pct > 0) {
    strikeRow = "<tr style='background:rgba(99,91,255,0.05);'><td><b>目标击穿价 (SAS)</b></td><td><b>-" +
      c.strike_drop_pct.toFixed(2) + "%</b></td><td><b>¥" + c.strike_price +
      "</b></td><td>最优停止临界点：跌至此价时等待净收益降为 0，触发买入</td></tr>";
  }
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
    money(c.net_yuan) + "</b></td><td>net>0 倾向等；否则买</td></tr>" +
    strikeRow + "</table>" +
    "<p class='muted'>[ref: decision.decomposition + 总纲 §2.5 / R05 §3 / SAS最优停止]</p>";
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
  var meta = {
    deadline: { title: "时间紧迫度", en: "DEADLINE HORIZON", opts: [["none", "不着急，能等到好价"], ["within_30", "一个月内"], ["within_90", "三个月内"], ["now", "必须马上有"]] },
    usage_intensity: { title: "使用频次", en: "USAGE INTENSITY", opts: [["rarely", "偶尔"], ["low", "每周 1-3 次"], ["medium", "每周 3-10h"], ["high", "重度每天用"]] },
    hedonic: { title: "消费动机", en: "PURCHASE MOTIVE", opts: [["utilitarian", "需要（影响正事）"], ["hedonic", "想要（升级体验）"]] },
    wait_tier: { title: "等待贴现档", en: "DISCOUNT TIER", opts: [["low", "贴现高·难等"], ["mid", "一般"], ["high", "贴现低·能等"]] },
    budget_tier: { title: "预算偏好", en: "BUDGET BRACKET", opts: [["low", "入门就够"], ["mid", "主流中档"], ["high", "旗舰顶配"], ["flexible", "看性价比"]] },
    price_view: { title: "价格走势预期", en: "PRICE OUTLOOK", opts: [["up", "感觉要涨"], ["stable", "平稳"], ["down", "会降"], ["uncertain", "说不准"]] },
    supply_news: { title: "供需舆情", en: "SUPPLY CLIMATE", opts: [["no", "缺货消息少"], ["yes", "缺货/涨价消息多"]] },
    alt_acceptable: { title: "平替/二手接受度", en: "SUBSTITUTION BIAS", opts: [["no", "只接受全新同款"], ["yes", "可接受二手/平替"]] }
  };

  var out = '<div class="sim-grid">';
  Object.keys(meta).forEach(function (k) {
    var item = meta[k];
    var cur = profile[k] != null ? profile[k] : item.opts[0][0];
    out += '<div class="sim-tile">' +
      '<div class="sim-tile-header">' +
        '<span class="sim-tile-title">' + item.title + '</span>' +
        '<span class="sim-tile-en">' + item.en + '</span>' +
      '</div>' +
      '<select id="ed-' + k + '" class="sim-select">' +
        item.opts.map(function (o) {
          return '<option value="' + o[0] + '"' + (o[0] === cur ? ' selected' : '') + '>' + o[1] + '</option>';
        }).join('') +
      '</select>' +
    '</div>';
  });
  out += '</div>';

  var purp = profile.purpose || "游戏";
  out += '<div class="sim-bottom-bar">' +
    '<div class="sim-purpose-wrap">' +
      '<div class="sim-purpose-header"><span class="sim-tile-title">核心应用场景</span><span class="sim-tile-en">PRIMARY USE CASE</span></div>' +
      '<select id="ed-purpose" class="sim-select">' +
        ["游戏", "AI / 跑模型", "3D / 视频创作", "编程 / 日常", "其他"].map(function (p) {
          return '<option' + (p === purp ? ' selected' : '') + '>' + p + '</option>';
        }).join('') +
      '</select>' +
    '</div>' +
    '<div class="sim-action-buttons">' +
      '<button id="btn-recalc" class="button btn-recompute">按新参数重算 (RECOMPUTE)</button>' +
      '<button id="btn-reset" class="button btn-reset">重置为问卷原答案 (RESET)</button>' +
    '</div>' +
  '</div>';
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
  var status = "<span id='hint-status' class='user-hint-msg'></span>";
  if (!S.user && !S.snap) {
    return "<div class='user-toolbar'>" +
      "<span class='user-status-pill'>游客模式 (GUEST)</span>" +
      "<span class='user-tip-text'>出卡已自动存档，登录后可同步多设备并开启变价关注预警</span>" +
      "<button id='btn-hint-login' class='button btn-user-action'>登录 / 注册</button>" +
      status +
    "</div>";
  }
  var parts = [];
  if (S.snap) {
    parts.push("<button id='btn-rerun' class='button btn-user-action'>用此画像重新出卡 →</button>");
    parts.push("<span class='user-tip-text'>历史快照 · " + esc(S.snap.at) + "</span>");
  } else if (S.user) {
    parts.push("<span class='user-status-pill on'>已登录: " + esc(S.user) + "</span>");
  }
  if (S.user && S.sku_id) {
    parts.push("<button id='btn-watch' class='button btn-user-action'>关注该商品</button>");
  }
  if (S.user && S.session_id && (S.savedState === "anon" || S.dirty)) {
    parts.push("<button id='btn-save-ver' class='button btn-user-action'>" +
      (S.dirty ? "另存为新历史" : "存入我的历史") + "</button>");
  }
  if (!parts.length) { return ""; }
  return "<div class='user-toolbar'>" + parts.join(" ") + status + "</div>";
}
function kpiQuartetHtml(card) {
  var st = card.stats, lb = st.lookbacks || {};
  var comp = card.decision && card.decision.decomposition;
  var cb = st.conformal_bounds || {};
  var mr = st.mean_reversion || {};
  var p90 = lb["90"] ? Math.round(lb["90"].pct_position * 100) : 0;
  var p365 = lb["365"] ? Math.round(lb["365"].pct_position * 100) : 0;

  var strikeHtml = (comp && comp.strike_price && comp.net_pct > 0)
    ? "<div class='kpi-tile'><div class='kpi-lbl'>SAS 击穿临界点</div><div class='kpi-val amber'>¥" + comp.strike_price + "</div><div class='kpi-sub'>降 -" + comp.strike_drop_pct.toFixed(1) + "% 触发买入</div></div>"
    : "<div class='kpi-tile'><div class='kpi-lbl'>SAS 状态</div><div class='kpi-val'>无击穿</div><div class='kpi-sub'>处于公允等待区间</div></div>";

  var conformalHtml = (cb.lower_bound && cb.upper_bound)
    ? "<div class='kpi-tile'><div class='kpi-lbl'>共形预测带 (90%)</div><div class='kpi-val'>¥" + cb.lower_bound + "~" + cb.upper_bound + "</div><div class='kpi-sub'>动态带宽 ±" + cb.bandwidth_pct + "% · 有限样本保证</div></div>"
    : "<div class='kpi-tile'><div class='kpi-lbl'>共形覆盖</div><div class='kpi-val'>--</div><div class='kpi-sub'>残差分位校准中</div></div>";

  var mrHtml = (mr.is_mean_reverting && mr.equilibrium_price)
    ? "<div class='kpi-tile'><div class='kpi-lbl'>OU 长期中枢</div><div class='kpi-val'>¥" + mr.equilibrium_price + "</div><div class='kpi-sub'>偏离 " + (mr.current_deviation_pct > 0 ? "+" : "") + mr.current_deviation_pct + "% · 半衰期 " + mr.half_life_days + " 天</div></div>"
    : "<div class='kpi-tile'><div class='kpi-lbl'>长期中枢</div><div class='kpi-val'>¥" + st.last_price + "</div><div class='kpi-sub'>价格平稳无结构偏离</div></div>";

  return "<div class='kpi-quartet'>" +
    "<div class='kpi-tile'>" +
      "<div class='kpi-lbl'>现价与分位</div>" +
      "<div class='kpi-val'>¥" + st.last_price + "</div>" +
      "<div class='kpi-meter-row'><div class='kpi-meter-bar'><div class='kpi-meter-fill' style='width:" + p90 + "%'></div></div><span class='kpi-meter-txt'>90D分位 " + p90 + "%</span></div>" +
      "<div class='kpi-sub'>1年历史分位 " + p365 + "%</div>" +
    "</div>" +
    strikeHtml +
    conformalHtml +
    mrHtml +
    "</div>";
}

function renderCard(card, profile, hist, keepEditorOpen, snap) {
  var snapNote = snap
    ? "<div class='cond' style='margin-bottom:1rem;'><b>历史快照</b> · 保存于 " + esc(snap.at || "") + "</div>"
    : "";

  var simHtml = "<div class='simulator-box'>" +
    "<div class='simulator-title-row'>" +
      "<div><span class='sim-pill'>CALIBRATION</span><h3 class='simulator-title'>参数推演模拟器 (HYPOTHESIS SIMULATOR)</h3></div>" +
      "<span class='sim-subtitle'>动态微调用户画像参数，实时推演边际效用与决策树分支</span>" +
    "</div>" +
    editorHtml(profile) +
    "</div>";

  var deepTelemetry = "<details class='telemetry-drawer'>" +
    "<summary>" +
      "<span>+ QUANTITATIVE TELEMETRY (点击展开数理分解、全口径表格与依据链)</span>" +
      "<span class='telemetry-pill'>5 MODELS AUDIT</span>" +
    "</summary>" +
    "<div class='telemetry-body' style='margin-top:1.2rem;'>" +
    p1Table(card) + decompTable(card) + conditionsHtml(card) + eventsHtml(card) + altTable(card) + evidenceHtml(card) +
    "</div>" +
    "</details>";

  return banner(card) +
    arbitrageCardHtml(card, profile) +
    priceSpectrumHtml(card) +
    kpiQuartetHtml(card) +
    chartCardHtml(card) +
    behavioralGridHtml(card) +
    snapNote +
    userBarHtml() +
    simHtml +
    deepTelemetry;
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
  if (!loggedIn()) { S.afterAuth = "view-me"; openAuth("login"); return; }
  S.afterAuth = null;
  show("view-me");
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
  var topNav = $("topbar-nav");
  if (topNav) {
    document.querySelectorAll(".tnav[data-view]").forEach(function (b) {
      var v = b.getAttribute("data-view");
      b.onclick = function () {
        if (v === "me") { openMe(); }
        else {
          document.querySelectorAll(".tnav[data-view]").forEach(function (x) { x.classList.toggle("on", x === b); });
          show(LAST_MAIN || "view-input");
          if (LAST_MAIN === "view-questions") { setStep(2); }
          else if (LAST_MAIN === "view-card") { setStep(3); }
          else { setStep(1); }
        }
      };
    });
  }
  $("btn-auth-go").onclick = doAuth;
  $("atab-login").onclick = function () {
    if (AUTH.mode !== "login") { AUTH.mode = "login"; authLabels(); $("auth-err").textContent = ""; }
  };
  $("atab-register").onclick = function () {
    if (AUTH.mode !== "register") { AUTH.mode = "register"; authLabels(); $("auth-err").textContent = ""; }
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

  /* Core-A Layout Toggle (List / Grid) */
  var btnList = $("btn-toggle-list");
  var btnGrid = $("btn-toggle-grid");
  var projWrap = $("projects-wrap");
  if (btnList && btnGrid && projWrap) {
    btnList.onclick = function () {
      btnList.classList.add("active");
      btnGrid.classList.remove("active");
      projWrap.classList.add("list-view");
      projWrap.classList.remove("grid-view");
      projWrap.setAttribute("data-view", "list");
    };
    btnGrid.onclick = function () {
      btnGrid.classList.add("active");
      btnList.classList.remove("active");
      projWrap.classList.add("grid-view");
      projWrap.classList.remove("list-view");
      projWrap.setAttribute("data-view", "grid");
    };
    projWrap.addEventListener("wheel", function (e) {
      if (projWrap.classList.contains("list-view") && Math.abs(e.deltaY) > 0) {
        e.preventDefault();
        projWrap.scrollLeft += e.deltaY;
      }
    }, { passive: false });
  }

  /* Core-A Project Showcase Cards Click */
  document.querySelectorAll(".project[data-sku]").forEach(function (card) {
    card.onclick = function () {
      var sku = card.getAttribute("data-sku");
      if (sku) {
        $("text").value = sku;
        resolveText(sku);
      }
    };
  });

  /* View Back Buttons */
  var bq = $("btn-back-from-q");
  if (bq) {
    bq.onclick = function () {
      show("view-input");
      setStep(1);
      setNav("view-input");
    };
  }
  var bc = $("btn-back-from-card");
  if (bc) {
    bc.onclick = function () {
      show("view-input");
      setStep(1);
      setNav("view-input");
    };
  }
  var bh = $("brand-home");
  if (bh) {
    bh.onclick = function () {
      show("view-input");
      setStep(1);
      setNav("view-input");
    };
  }

  /* Core-A Live Ticking Footer Clocks (SEL / BJS / LDN) */
  function updateClocks() {
    var now = new Date();
    var utc = now.getTime() + (now.getTimezoneOffset() * 60000);
    var seoul = new Date(utc + (3600000 * 9));
    var beijing = new Date(utc + (3600000 * 8));
    var london = new Date(utc);

    function pad2(n) { return (n < 10 ? "0" : "") + n; }
    function fmt(d) {
      return pad2(d.getHours()) + ":" + pad2(d.getMinutes()) + ":" + pad2(d.getSeconds());
    }
    var elKr = $("clock-kr");
    var elBj = $("clock-bj");
    var elLdn = $("clock-ldn");
    if (elKr) elKr.textContent = fmt(seoul);
    if (elBj) elBj.textContent = fmt(beijing);
  }
  updateClocks();
  setInterval(updateClocks, 1000);
  /* Core-A Rotary Dial Menu (Top: History, Middle: Showcase, Bottom: Auth) */
  var dHist = $("dial-item-history");
  if (dHist) {
    dHist.onclick = function () {
      show("pane-history");
      meTab("history");
    };
  }
  var dShow = $("dial-item-showcase");
  if (dShow) {
    dShow.onclick = function () {
      show("pane-showcase");
    };
  }
  var dAuth = $("dial-item-auth");
  if (dAuth) {
    dAuth.onclick = function () {
      show("pane-auth");
      refreshUserBar();
    };
  }

  var btnInLogout = $("btn-inpage-logout");
  if (btnInLogout) {
    btnInLogout.onclick = function () {
      doLogout();
      refreshUserBar();
    };
  }

  initSession();
});

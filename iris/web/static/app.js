/* Iris Web 前端：输入 -> 画像问卷 -> 决策卡（假设编辑 + 重算历史）。离线无 CDN。
 * 交互约定：点选选项 = 自动进入下一题（260ms 高亮反馈）；可点「上一题」修改；
 * 最后一题点选后自动提交出卡。
 */
"use strict";

var S = { product: null, sku_id: null, questions: [], flow: null,
          answers: {}, session_id: null, card: null, profile: null };

var $ = function (id) { return document.getElementById(id); };
function esc(x) {
  return String(x == null ? "" : x).replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
function api(path, body) {
  var opt = { method: "POST", headers: { "Content-Type": "application/json" },
              body: JSON.stringify(body) };
  return fetch(path, opt).then(function (r) {
    return r.json().then(function (j) {
      if (!r.ok) { throw new Error(j.detail || j.error || ("HTTP " + r.status)); }
      return j;
    });
  });
}
function show(id) {
  ["view-input", "view-questions", "view-card"].forEach(function (v) {
    $(v).classList.toggle("hidden", v !== id);
  });
  window.scrollTo(0, 0);
}
function setStep(i) {
  ["step-i", "step-q", "step-c"].forEach(function (s, k) { $(s).classList.toggle("on", k < i); });
}

/* ---------- 第一步：解析 ---------- */
function resolveText(text) {
  $("btn-resolve").disabled = true;
  $("resolve-out").innerHTML = '<p class="tip">解析中…</p>';
  api("/api/resolve", { text: text }).then(function (j) {
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
        api("/api/resolve", { text: text, name: $("m-name").value, category: $("m-cat").value })
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
  S.flow = j.flow; S.answers = {};
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
  if (b) { b.onclick = function () { startQuestions(); }; }
}
function chipFill() {
  document.querySelectorAll(".chip").forEach(function (c) {
    c.onclick = function () { $("text").value = c.getAttribute("data-ex"); };
  });
}

/* ---------- 第二步：画像问卷（点选自动下一题） ---------- */
var Q = { items: [], idx: 0, picked: {}, timer: null };
function startQuestions() {
  Q.items = [];
  (S.questions || []).forEach(function (q) {
    if (q.type === "group") {
      (q.items || []).forEach(function (it) {
        Q.items.push({ text: it.text, id: it.id, options: it.options });
      });
    } else { Q.items.push(q); }
  });
  Q.idx = 0; Q.picked = {};
  show("view-questions");
  setStep(2);
  var flowTxt = S.flow === "essential"
    ? "必需品类：时点不重要 —— 回答 3 题后直达「直接买 + 渠道比价」结论"
    : "完整时机问卷：" + Q.items.length + " 题（含 3 道「等多久换折扣」测评题）";
  $("q-flow").textContent = "商品：" + S.product.name + " ｜ " + flowTxt;
  renderQ();
}
function renderQ() {
  var q = Q.items[Q.idx];
  $("q-nav").classList.remove("hidden");
  $("btn-prev").classList.toggle("hidden", Q.idx === 0);
  $("q-body").innerHTML = '<p class="progress">第 ' + (Q.idx + 1) + " / " +
    Q.items.length + " 题（点选选项自动进入下一题，可随时「上一题」修改）</p>" +
    '<p class="q-text">' + esc(q.text) + "</p>";
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
  if (Q.picked[q.id] != null && Q.idx < Q.items.length - 1) {
    var cont = document.createElement("button");
    cont.type = "button";
    cont.className = "ghost";
    cont.textContent = "继续 →（不改则直接前进）";
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
  api("/api/answer", { product: S.product, sku_id: S.sku_id, answers: S.answers })
    .then(function (j) {
      S.session_id = j.session_id; S.profile = j.profile; S.card = j.card;
      if (j.card) { showCard(j.card); }
      else {
        show("view-card"); setStep(3);
        $("no-data").classList.remove("hidden");
        $("no-data").innerHTML =
          '<div class="panel"><h3>流程结论（无价格库，未出量化卡）</h3><p>' +
          esc(j.note || "demo 库暂无该型号数据") + "</p>" +
          '<p class="muted">画像已记录：' + esc(JSON.stringify(j.profile)) + "</p></div>";
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
function pct1(x) { return x == null ? "--" : (x * 100).toFixed(0) + "%"; }
function pct2(x) { return x == null ? "--" : (x * 100).toFixed(2) + "%"; }
function money(x) { return x == null ? "--" : "¥" + Math.round(x); }

function showCard(card) {
  $("no-data").classList.add("hidden");
  show("view-card"); setStep(3);
  $("card-root").innerHTML = renderCard(card, S.profile, []);
  bindCardEvents(card);
}
function banner(card) {
  var d = card.decision;
  var k = LIGHT_KEY[d.traffic_light] || "yellow";
  var recTxt = { buy: "现在买", wait: "先等一等", switch: "换一个买" }[d.recommendation] || d.recommendation;
  return '<div class="banner ' + k + '"><div><span class="light-dot ' + k + '"></span>' +
    "<div class='big'>" + recTxt + "　" + LIGHT[d.traffic_light] + "</div>" +
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
    money(c.net_yuan) + "</b></td><td>net&gt;0 倾向等；否则买</td></tr></table>" +
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
function renderCard(card, profile, hist) {
  var d = card.decision;
  return "<div class='panel'>" + banner(card) + "</div>" +
    "<div class='panel'><h3>K 线与价格统计 <span class='badge'>合成数据</span></h3>" +
    "<div id='kline-box'></div>" + kpiRow(card) +
    "<p class='muted'>周线（自绘 SVG，离线可用）；现价 " + card.stats.last_price +
    " 元（" + card.stats.asof + "）｜MA20 " + (card.stats.ma["20"] || "-") +
    "｜MA60 " + (card.stats.ma["60"] || "-") + "｜90 天波动率分位 " +
    ((card.stats.volatility.pct_position || 0) * 100).toFixed(0) + "%</p></div>" +
    "<div class='grid2'><div class='panel'><h3>P1 · 降价概率（客观频率）</h3>" +
    p1Table(card) + "</div>" +
    "<div class='panel'><h3>决策分解（G / U / R / buffer）</h3>" + decompTable(card) + "</div></div>" +
    "<div class='panel'><h3>条件句（若……则……）</h3>" + conditionsHtml(card) + "</div>" +
    "<div class='grid2'><div class='panel'><h3>事件日历（R01）</h3>" + eventsHtml(card) +
    "</div><div class='panel'><h3>替代品矩阵（R03）</h3>" + altTable(card) + "</div></div>" +
    "<div class='panel'><h3>假设编辑器（改参数 → 重算 P2/红绿灯）</h3>" + editorHtml(profile) +
    "<h4>重算记录</h4><div id='hist-box'>" + historyHtml(hist) + "</div></div>" +
    "<div class='panel'><h3>依据链（每个数字可展开口径 / 样本 / 假设）</h3>" +
    evidenceHtml(card) + "</div>";
}
function bindCardEvents(card) {
  var kbox = $("kline-box");
  if (kbox) {
    fetch("/api/kline?sku_id=" + encodeURIComponent(card.meta.sku_id))
      .then(function (r) { return r.text(); })
      .then(function (svg) { kbox.innerHTML = svg; })
      .catch(function () { kbox.innerHTML = "<p class='tip'>K 线加载失败</p>"; });
  }
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
      api("/api/recompute", { session_id: S.session_id, overrides: over })
        .then(function (j) {
          S.profile = j.profile;
          $("card-root").innerHTML = renderCard(j.card, j.profile, j.history);
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
      api("/api/recompute", { session_id: S.session_id, overrides: {} })
        .then(function (j) {
          S.profile = j.profile;
          $("card-root").innerHTML = renderCard(j.card, j.profile, j.history);
          bindCardEvents(j.card);
        }).catch(function (e) { alert("重置失败：" + e.message); });
    };
  }
}

/* ---------- 初始化 ---------- */
document.addEventListener("DOMContentLoaded", function () {
  $("btn-resolve").onclick = function () { resolveText($("text").value); };
  $("btn-prev").onclick = prevQ;
  chipFill();
});

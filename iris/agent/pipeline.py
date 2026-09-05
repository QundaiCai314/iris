# -*- coding: utf-8 -*-
"""M6 全链路管线（CLI 与 Web 共用）：商品解析 -> 画像 -> 全字段决策卡。

- load_demo(): 载入 demo 数据（模块级缓存，进程内单次加载）。
- resolve_product(text): 文本 -> {product, sku_id, catalog_hit}（规则解析，M4.3 无 LLM 兜底）。
- build_card(profile_dict, sku_id): 画像 + SKU -> 决策卡 JSON（stats/P1/事件/替代/P2/条件句/依据链）。
- SCENARIOS: 三个演示画像（scripts/make_decision_demo.py 与 CLI/Web 示例共用）。

口径与出处：stats=p1=total 纲 §2.1-2.2；events=R01；alternatives=R03 降级；
decision=总纲 §2.5 + R05 §3（A1-A7 假设见 docs/decisions.md D5）。
"""
from __future__ import annotations
import os
from datetime import date, timedelta
from typing import Dict, List, Optional

from iris.agent.needs import detect_model, parse_product_text
from iris.core.alternatives import best_switch, build_rows
from iris.core.behavior import build_behavior_hints
from iris.core.card import build_card as card_build, validate_card
from iris.core.decision import build_decision
from iris.core.events import build_event_study
from iris.core.p1 import forecast_windows
from iris.core.prices import load_all, load_events, resample_ohlc
from iris.core.stats import describe

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEMO_DIR = os.path.join(ROOT, "data", "demo")

# 型号匹配顺序：更长 token 优先（5070ti 必须先于 5070 判定）
MODEL_TOKENS = [("5070ti", "rtx5070ti"), ("5080", "rtx5080"), ("5070", "rtx5070")]

SCENARIOS = [
    {"key": "gpu_high", "label": "5080 玩家·价高位·可等可换",
     "sku": "rtx5080-asus-tuf-mid",
     "profile": {"name": "华硕 RTX 5080 TUF", "category": "显卡", "source": "demo",
                 "necessity": "optional", "purpose": "游戏", "deadline": "none",
                 "usage_intensity": "medium", "budget_tier": "flexible",
                 "alt_acceptable": "yes", "hedonic": "hedonic",
                 "wait_tier": "mid", "price_view": "up", "supply_news": "yes"}},
    {"key": "gpu_low", "label": "5070 日常用·低位平台·预算紧",
     "sku": "rtx5070-gigabyte-mid",
     "profile": {"name": "技嘉 RTX 5070", "category": "显卡", "source": "demo",
                 "necessity": "optional", "purpose": "编程 / 日常", "deadline": "within_90",
                 "usage_intensity": "low", "budget_tier": "low",
                 "alt_acceptable": "no", "hedonic": "utilitarian",
                 "wait_tier": "high", "price_view": "stable", "supply_news": "no"}},
    {"key": "gpu_pdd", "label": "5080 拼多多渠道·只认全新同款",
     "sku": "rtx5080-msi-ventus-entry-pdd",
     "profile": {"name": "微星 RTX 5080 VENTUS", "category": "显卡", "source": "demo",
                 "necessity": "optional", "purpose": "游戏", "deadline": "within_30",
                 "usage_intensity": "high", "budget_tier": "mid",
                 "alt_acceptable": "no", "hedonic": "hedonic",
                 "wait_tier": "low", "price_view": "stable", "supply_news": "no"}},
]

_demo_cache: Optional[Dict] = None


def load_demo() -> Dict:
    """demo 数据 + 现价表（模块级缓存）。"""
    global _demo_cache
    if _demo_cache is None:
        products, skus, series = load_all(os.path.join(DEMO_DIR, "prices"),
                                          os.path.join(DEMO_DIR, "catalog.json"))
        events = load_events(os.path.join(DEMO_DIR, "events.json"))
        price_map = {}
        for sid, ser in series.items():
            if ser.points:
                price_map[sid] = ser.points[-1].price
        _demo_cache = {"products": products, "skus": skus, "series": series,
                       "events": events, "price_map": price_map}
    return _demo_cache


def match_sku(text: str) -> Optional[str]:
    """文本/型号 -> demo SKU（显卡场景）；返回 None 表示库中无此型号。"""
    d = load_demo()
    norm = (text or "").lower().replace(" ", "").replace("-", "").replace("_", "")
    product_id = None
    for token, pid in MODEL_TOKENS:
        if token in norm:
            product_id = pid
            break
    if product_id is None:
        return None
    # 默认 SKU：catalog 中该 product 的第一条（asus/jd 主渠道）
    for sid, s in d["skus"].items():
        if s.product_id == product_id and s.channel == "jd":
            return sid
    for sid, s in d["skus"].items():
        if s.product_id == product_id:
            return sid
    return None


def resolve_product(text: str) -> Dict:
    """文本 -> {product, sku_id, catalog_hit, message}。解析失败走手动确认（M4.3）。"""
    p = parse_product_text(text)
    sku_id = None
    hit = bool(p.get("category"))
    message = ""
    if p.get("category"):
        sku_id = match_sku(text)
        if sku_id is None:
            hit = False
            message = ("识别为 %s，但 demo 价格库只有显卡型号（RTX 5080 / 5070 Ti / "
                       "5070）；该品类可继续跑问卷流程演示，无法出量化卡。"
                       % p["category"])
    else:
        message = "没认出品类/型号：请手动确认商品名与品类后继续。"
    return {"product": {"name": p.get("name"), "category": p.get("category"),
                        "source": p.get("source", "text")},
            "sku_id": sku_id, "catalog_hit": bool(sku_id), "message": message}


def _event_summary_text(study: Dict, etype: str, horizon: str = "60") -> Optional[str]:
    s = (study.get(etype) or {}).get("horizons", {}).get(horizon) or {}
    if not s or not s.get("n"):
        return None
    return ("历史 %d 起 %s 事件，%s 天窗平均 %+.2f%%（n=%d，仅量级参考）"
            % (s["n"], etype, horizon, s["mean_pct"] or 0, s["n"]))


def build_events_slim(product_id: str, asof: date) -> Dict:
    """产品级事件研究摘要 + asof 后 180 天内匹配事件（upcoming）。"""
    d = load_demo()
    slim = {}
    for t in ("promo", "supply", "launch"):
        st = build_event_study(d["series"], d["skus"], d["products"], d["events"],
                               product_id, event_type=t)
        if t in st:
            slim[t] = {"horizons": st[t]["horizons"],
                       "control_used": st[t]["control_used"],
                       "control_note": st[t]["control_note"]}
    upcoming = []
    for ev in d["events"]:
        evd = date.fromisoformat(ev.date)
        delta = (evd - asof).days
        if delta <= 0 or delta > 180:
            continue
        if ev.scope != "all" and product_id not in [x.strip()
                                                    for x in ev.scope.split(",")]:
            continue
        item = {"type": ev.type, "title": ev.title, "date": ev.date,
                "days_ahead": delta, "beyond_days": max(0, delta - 60),
                "confidence": ev.confidence}
        txt = _event_summary_text(slim, ev.type) if ev.type in slim else None
        if txt:
            item["summary_text"] = txt
        upcoming.append(item)
    slim["upcoming"] = upcoming
    return slim


def evidence_for(profile: Dict, fcw: Dict, slim: Dict) -> List[Dict]:
    ev = [
        {"ref": "data: synthetic-demo",
         "note": "演示价序列为合成剧本（含真实量级锚点），非真实抓取；结论仅演示引擎"},
        {"ref": "p1.windows.60",
         "note": "P1 = 同分位段历史窗口降价频率，n=%s，Wilson 95%% CI（R04）"
                 % (fcw.get("60") or {}).get("n")},
        {"ref": "stats.lookbacks.365/730", "note": "时间参考锚：现价近 1/2 年分位（总纲 §1.4）"},
    ]
    for t in ("promo", "supply", "launch"):
        h = ((slim.get(t) or {}).get("horizons") or {}).get("60") or {}
        if h:
            ev.append({"ref": "events.%s" % t,
                       "note": "事件研究 %s：horizon60 mean=%s%% n=%s（R01；n<30 仅参考）"
                       % (t, h.get("mean_pct"), h.get("n"))})
    ev.append({"ref": "R03 §2-4",
               "note": "替代矩阵属性近邻配对；品牌/售后/生态不可观测项标注「值不值由你判断」"})
    ev.append({"ref": "R05 §3 + 假设 A1-A7",
               "note": "U 参数方向有出处（享乐品等待成本更高、贴现档位映射），数值待 B05 标定，展示可调"})
    ev.append({"ref": "总纲 §2.5 + §1.2",
               "note": "裁决 = G - U - R - buffer；buffer 随波动率分位加宽（(S,s)）"})
    return ev


def build_card(profile: Dict, sku_id: str, rerun_count: int = 0,
               just_resolved: bool = False) -> Dict:
    """画像 + SKU -> 全字段决策卡（M6 端到端主入口）。"""
    d = load_demo()
    if sku_id not in d["skus"]:
        raise ValueError("SKU 不在 demo 库: %s" % sku_id)
    sku = d["skus"][sku_id]
    ser = d["series"][sku_id]
    stats = describe(ser.points)
    fcw = forecast_windows(ser.points)
    asof = date.fromisoformat(stats["asof"])
    slim = build_events_slim(sku.product_id, asof)
    mx = build_rows(sku_id, d["products"], d["skus"], d["price_map"],
                    purpose=profile.get("purpose"))
    best = best_switch(sku_id, d["products"], d["skus"], d["price_map"],
                       purpose=profile.get("purpose"),
                       alt_acceptable=profile.get("alt_acceptable", "no"))
    vol = stats["volatility"]["pct_position"]
    dec = build_decision(profile, fcw, vol, best_alt=best,
                         upcoming=slim.get("upcoming"))
    card = card_build(sku.product_id, sku_id, stats["asof"], stats, fcw,
                      engine_version="0.3.0")
    card["events"] = slim
    card["alternatives"] = mx
    card["decision"] = dec
    card["evidence"] = evidence_for(profile, fcw, slim)
    card["kline"] = resample_ohlc(ser.points, freq_days=7)   # 周 OHLC（CLI/Web 渲染用）
    card["behavior_hints"] = build_behavior_hints(
        card, rerun_count=rerun_count, just_resolved=just_resolved)
    errs = validate_card(card)
    if errs:
        raise ValueError("决策卡校验失败: %s" % errs)
    return card

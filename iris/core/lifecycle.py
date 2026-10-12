# -*- coding: utf-8 -*-
"""生命周期代理曲线（M3.2；出处：R02 §3）。

曲线文件：data/lifecycle/<family>.json，字段 {family, source_note, curve:[[月, 上市价比例], ...]}。
插值：分段线性。输出一律带 proxy=True（R02：新品无自身历史时的代理估计，界面须标「代理数据」）。
"""
from __future__ import annotations
import json
import os
from datetime import date
from typing import Dict, List, Optional

DEFAULT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                           "data", "lifecycle")


def list_families(directory: str = DEFAULT_DIR) -> List[str]:
    if not os.path.isdir(directory):
        return []
    return [f[:-5] for f in os.listdir(directory) if f.endswith(".json")]


def load_family(family: str, directory: str = DEFAULT_DIR) -> Dict:
    path = os.path.join(directory, family + ".json")
    if not os.path.exists(path):
        raise FileNotFoundError("生命周期曲线族不存在: %s（可用: %s）"
                                % (family, ",".join(list_families(directory))))
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    raw["curve"] = [(float(m), float(pct)) for m, pct in raw["curve"]]
    return raw


def pct_at_month(family_data: Dict, months: float) -> float:
    """分段线性插值；超出曲线范围用端点值（clamp）。"""
    curve = family_data["curve"]
    if months <= curve[0][0]:
        return curve[0][1]
    if months >= curve[-1][0]:
        return curve[-1][1]
    for (m0, p0), (m1, p1) in zip(curve, curve[1:]):
        if m0 <= months <= m1:
            t = (months - m0) / (m1 - m0) if m1 != m0 else 0.0
            return p0 * (1 - t) + p1 * t
    return curve[-1][1]


def expect_price(launch_price: int, launch_date: str, at_date: str, family: str,
                 directory: str = DEFAULT_DIR) -> Dict:
    """新品（无自身历史）的代理期望价。输出打 proxy 标签。"""
    fam = load_family(family, directory)
    months = max(0.0, (date.fromisoformat(at_date) - date.fromisoformat(launch_date)).days / 30.44)
    pct = pct_at_month(fam, months)
    return {"family": family, "months_since_launch": round(months, 1),
            "price_pct": round(pct, 4), "expect_price": int(round(launch_price * pct)),
            "proxy": True, "source_note": fam["source_note"]}


CATEGORY_CYCLES_DAYS = {
    "phone": 365,      # 手机一般 12 个月换代
    "gpu": 730,        # 显卡一般 24 个月跨代换代
    "console": 2555,   # 主机一般 7 年大代际
    "laptop": 365,     # 笔电随 CPU/GPU 每年刷新
    "default": 730,
}

CLEARANCE_HURDLES_PCT = {
    "phone": 28.0,     # 手机临换代老款至少需降 28%
    "gpu": 35.0,       # 显卡临换代老款至少需降 35%
    "console": 20.0,
    "laptop": 25.0,
    "default": 30.0,
}


def analyze_backstab_risk(category: str, launch_date_str: str,
                          current_price: float, launch_price: float,
                          asof_str: Optional[str] = None) -> Dict:
    """耐用品生命周期与背刺风险指数（BRI）。
    计算已上市时长、距下代预测天数、清仓补偿门槛与背刺风险指数。
    """
    asof = date.fromisoformat(asof_str) if asof_str else date.today()
    launch_d = date.fromisoformat(launch_date_str)

    cat_key = (category or "default").lower()
    cycle_days = CATEGORY_CYCLES_DAYS.get(cat_key, CATEGORY_CYCLES_DAYS["default"])
    hurdle_pct = CLEARANCE_HURDLES_PCT.get(cat_key, CLEARANCE_HURDLES_PCT["default"])

    elapsed_days = max(0, (asof - launch_d).days)
    progress = max(0.0, elapsed_days / cycle_days)
    days_to_next = max(0, int(cycle_days - (elapsed_days % cycle_days)))

    drawdown_pct = max(0.0, (launch_price - current_price) / launch_price * 100.0) if launch_price > 0 else 0.0

    if progress < 0.25:
        phase = "Phase 1: 首发导入期"
    elif progress < 0.65:
        phase = "Phase 2: 成熟放量期"
    elif progress < 0.90:
        phase = "Phase 3: 换代预警期"
    else:
        phase = "Phase 4: 清仓退市期"

    time_urgency = max(0.0, 1.0 - (days_to_next / 180.0))
    bri = time_urgency / (1.0 + drawdown_pct / 100.0)
    bri = round(min(1.0, max(0.0, bri)), 3)

    if bri >= 0.65:
        risk_level = "high"
    elif bri >= 0.35:
        risk_level = "medium"
    else:
        risk_level = "low"

    hurdle_met = drawdown_pct >= hurdle_pct
    return {
        "category": category,
        "elapsed_days": elapsed_days,
        "days_to_next_gen": days_to_next,
        "current_drawdown_pct": round(drawdown_pct, 2),
        "phase": phase,
        "bri": bri,
        "risk_level": risk_level,
        "hurdle_threshold_pct": hurdle_pct,
        "hurdle_met": hurdle_met,
    }


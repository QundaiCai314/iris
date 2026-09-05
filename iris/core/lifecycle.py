# -*- coding: utf-8 -*-
"""生命周期代理曲线（M3.2；出处：R02 §3）。

曲线文件：data/lifecycle/<family>.json，字段 {family, source_note, curve:[[月, 上市价比例], ...]}。
插值：分段线性。输出一律带 proxy=True（R02：新品无自身历史时的代理估计，界面须标「代理数据」）。
"""
from __future__ import annotations
import json
import os
from datetime import date
from typing import Dict, List

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

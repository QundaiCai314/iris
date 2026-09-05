# -*- coding: utf-8 -*-
"""P1 概率校准检查（M2.4；口径：总纲 §2.2 与 R04 §2）。

流程：沿历史每 step_days 天取一个 asof（要求 asof 之前已有足够历史、之后有完整 window_days 结果），
对每个 asof 用当时数据跑 p1_forecast -> 预测 p；观察未来 window_days 是否真实降价 >= drop -> 结果 0/1。
评估：可靠性分箱（等频 5 箱，箱内样本 < 5 跳过并标注）、Brier、最大偏差；偏差 > 0.1 触发降级建议。
"""
from __future__ import annotations
from datetime import date, timedelta
from typing import Dict, List, Tuple

from iris.core.models import PricePoint
from iris.core.p1 import p1_forecast
from iris.core.stats import _d

MAX_DEV = 0.10


def _is_drop(points: List[PricePoint], asof_idx: int, window_days: int, drop: float) -> bool:
    last = points[asof_idx].price
    threshold = last * (1 - drop)
    d0 = _d(points[asof_idx])
    for p in points[asof_idx + 1:]:
        if (_d(p) - d0).days > window_days:
            break
        if p.price <= threshold:
            return True
    return False


def collect_pairs(points: List[PricePoint], window_days: int = 60, drop: float = 0.05,
                  step_days: int = 30, min_history_days: int = 365,
                  lookback_days: int = 365) -> Tuple[List[tuple], List[str]]:
    """返回 ([(p, outcome), ...], notes)。只用当时可得数据（无前视）。"""
    pairs: List[tuple] = []
    notes: List[str] = []
    for i, pt in enumerate(points):
        if i < 2:      # 占位防 lint；实际条件在下方
            pass
    asof_candidates = []
    for i in range(len(points)):
        d0 = _d(points[i])
        if (d0 - _d(points[0])).days < min_history_days:
            continue
        if len(points) - 1 - i < window_days // 2:
            continue  # 之后没有完整结果窗
        if asof_candidates and (d0 - _d(points[asof_candidates[-1]])).days < step_days:
            continue
        asof_candidates.append(i)
    for i in asof_candidates:
        if len(points) - 1 - i < window_days:   # 结果窗不完整 -> 跳过（防前视/残缺）
            continue
        fc = p1_forecast(points, asof_idx=i, window_days=window_days, drop=drop,
                         lookback_days=lookback_days, min_n=1)
        p = fc.get("probability")
        if p is None:      # 历史点自身样本不足时仍可记方向，但概率校准只用有概率的
            continue
        outcome = 1 if _is_drop(points, i, window_days, drop) else 0
        pairs.append((p, outcome))
    if len(pairs) < 10:
        notes.append("校准样本过少(%d)，结论仅作流程演示" % len(pairs))
    return pairs, notes


def reliability(pairs: List[tuple], nbins: int = 5) -> Dict:
    """等频分箱可靠性：每箱 avg_p vs 实际频率。样本 <5 的箱跳过。"""
    if not pairs:
        return {"bins": [], "brier": None, "max_dev": None, "n": 0}
    s = sorted(pairs, key=lambda x: x[0])
    bins = []
    n_per = max(1, len(s) // nbins)
    for b in range(nbins):
        chunk = s[b * n_per:(b + 1) * n_per] if b < nbins - 1 else s[b * n_per:]
        if len(chunk) < 5:
            continue
        avg_p = sum(x[0] for x in chunk) / len(chunk)
        freq = sum(x[1] for x in chunk) / len(chunk)
        bins.append({"n": len(chunk), "avg_p": round(avg_p, 3), "frequency": round(freq, 3),
                     "dev": round(freq - avg_p, 3)})
    brier = sum((p - o) ** 2 for p, o in pairs) / len(pairs)
    devs = [abs(b["dev"]) for b in bins]
    return {"n": len(pairs), "bins": bins, "brier": round(brier, 4),
            "max_dev": max(devs) if devs else None,
            "degraded": (max(devs) if devs else 0) > MAX_DEV}


def run_report(points: List[PricePoint], label: str = "sku") -> Dict:
    pairs, notes = collect_pairs(points)
    rep = reliability(pairs)
    rep.update({"label": label, "notes": notes,
                "rule": "max|dev|>%.2f -> 降级为仅方向输出（R04 §2）" % MAX_DEV})
    return rep

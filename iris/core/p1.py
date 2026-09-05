# -*- coding: utf-8 -*-
"""P1：未来 window_days 天降价 >= drop 的概率（历史模拟频率法）。

口径（总纲 §2.2 / R04 §2，方法 v1）：
- 候选历史日 j：仅在 asof 之前（无前视）；j 之前须有 min_history_days 天数据（可算分位段）。
- 与当前「同分位段」：将历史日 j 的价格在 j 前 lookback_days 窗口的分位位置归入 buckets 个等宽分位段；
  只统计与当前价格分位段相同的历史日。
- 事件相位修正（换代 / 大促窗口）由 M3 事件层以乘数/条件输出给出（方法 v2），v1 不混入。
- 输出：n>=min_n 时点估计 + Wilson 95% 区间；n<min_n 时不给点概率，只给方向与幅度分位（总纲样本纪律）。
"""
from __future__ import annotations
import math
from datetime import date, timedelta
from typing import Dict, List, Optional

from iris.core.models import PricePoint
from iris.core.stats import _calendar_window, _d, percentile_position

WILSON_Z = 1.96


def wilson_ci(hits: int, n: int, z: float = WILSON_Z) -> tuple:
    """Wilson score interval（小样本优于正态近似）。"""
    if n == 0:
        return (0.0, 0.0)
    p = hits / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def _future_low(points: List[PricePoint], j: int, window_days: int,
                cap_idx: Optional[int] = None) -> Optional[int]:
    """j 日之后 window_days 天内最低价（不含 j 当日）。cap_idx 防前视：只看到 asof。"""
    d0 = _d(points[j])
    end = len(points) if cap_idx is None else min(len(points), cap_idx + 1)
    lo_price = None
    for k in range(j + 1, end):
        p = points[k]
        d = _d(p)
        if (d - d0).days > window_days:
            break
        lo_price = p.price if lo_price is None else min(lo_price, p.price)
    return lo_price


def p1_forecast(points: List[PricePoint], asof_idx: int = -1,
                window_days: int = 60, drop: float = 0.05,
                lookback_days: int = 365, min_history_days: int = 120,
                buckets: int = 4, min_n: int = 30) -> Dict:
    """返回 P1 结果字典（口径字段齐全，供决策卡依据链使用）。"""
    if not points:
        raise ValueError("空价格序列")
    if asof_idx < 0:
        asof_idx = len(points) - 1
    last = points[asof_idx].price
    asof = _d(points[asof_idx])

    # 当前分位段
    cur_win = _calendar_window(points, asof_idx, lookback_days)
    cur_pos = percentile_position(last, [p.price for p in cur_win])
    cur_bucket = min(buckets - 1, int((cur_pos or 0.0) * buckets))

    hits, lows, n_cand = 0, [], 0
    cand_dates = []
    lo_date = asof - timedelta(days=min_history_days)
    threshold = last * (1 - drop)
    for j in range(asof_idx):
        d0 = _d(points[j])
        if d0 > asof - timedelta(days=30):   # 太接近 asof 的候选未来窗不完整，跳过
            continue
        if d0 > lo_date or d0 < lo_date - timedelta(days=365 * 3):
            continue
        win = _calendar_window(points, j, lookback_days)
        vals = [p.price for p in win]
        pos = percentile_position(points[j].price, vals)
        if pos is None:
            continue
        if min(buckets - 1, int(pos * buckets)) != cur_bucket:
            continue
        fut = _future_low(points, j, window_days, cap_idx=asof_idx)
        if fut is None:
            continue
        n_cand += 1
        cand_dates.append(d0)
        lows.append(fut)
        if fut <= threshold:
            hits += 1

    n = len(lows)
    res: Dict = {
        "window_days": window_days,
        "drop": drop,
        "asof": asof.isoformat(),
        "last_price": last,
        "threshold": round(threshold, 2),
        "bucket": cur_bucket,
        "buckets": buckets,
        "percentile_position": round(cur_pos, 4) if cur_pos is not None else None,
        "method": "v1-history-frequency",
        "method_note": "同分位段历史窗口频率；事件相位修正由 M3 提供（v2）",
        "n": n,
        "n_sufficient": n >= min_n,
        "min_n": min_n,
        "sample": {
            "first_date": min(cand_dates).isoformat() if cand_dates else None,
            "last_date": max(cand_dates).isoformat() if cand_dates else None,
            "span_days": (max(cand_dates) - min(cand_dates)).days if len(cand_dates) > 1 else 0,
            "note": ("候选集中于单一行情段(跨度<90天)，非独立样本"
                       if len(cand_dates) > 1 and (max(cand_dates) - min(cand_dates)).days < 90 else "ok"),
        },
    }

    # 等待策略统计（M5 决策引擎 G/R 数据输入；口径：等满 window_days 天、以窗内最低价成交，
    # 最低价低于现价记节省 saving，高于现价记损失 loss；均为全部候选窗口的无条件均值 pct）
    if lows:
        _sv = [max(0.0, (last - f) / last) * 100.0 for f in lows]
        _ls = [max(0.0, (f - last) / last) * 100.0 for f in lows]
        res["wait_stats"] = {
            "n_windows": len(lows),
            "saving_pct": round(sum(_sv) / len(_sv), 4),
            "loss_pct": round(sum(_ls) / len(_ls), 4),
            "net_pct": round((sum(_sv) - sum(_ls)) / len(_ls), 4),
        }
    else:
        res["wait_stats"] = None
    if n >= min_n:
        p = hits / n
        lo_ci, hi_ci = wilson_ci(hits, n)
        res.update({
            "probability": round(p, 4),
            "ci95": [round(lo_ci, 4), round(hi_ci, 4)],
            "hits": hits,
            "direction": "down" if p > 0.5 else ("up" if p < 0.5 else "flat"),
            "confidence": "sufficient",
        })
    else:
        # 小样本：不给点概率，只给方向 + 历史幅度分位
        if lows:
            s = sorted(lows)
            med = s[len(s) // 2]
            q25 = s[len(s) // 4]
            res.update({
                "probability": None,
                "ci95": None,
                "hits": hits,
                "median_future_low": med,
                "low_q25": q25,
                "direction": "down" if med < threshold else ("up" if med > last else "flat"),
                "confidence": "insufficient",
            })
        else:
            res.update({"probability": None, "ci95": None, "hits": 0,
                        "direction": "unknown", "confidence": "insufficient"})
    return res


def forecast_windows(points: List[PricePoint], asof_idx: int = -1,
                     windows: tuple = (30, 60, 180), drop: float = 0.05) -> Dict:
    """P1 主/辅窗口集（默认 60 主，30/180 辅；定版参数：用户 2026-09-04）。"""
    return {str(w): p1_forecast(points, asof_idx=asof_idx, window_days=w, drop=drop)
            for w in windows}

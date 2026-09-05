# -*- coding: utf-8 -*-
"""滚动统计原语（M2.1；口径出处：总纲 §2.1 与 docs/data-schema.md §5）。纯标准库。

统一口径：
- 回看窗口 = 日历窗口（asof 往前 L 天内的点）；MA 例外按点数窗口（日度数据 ≈ 交易日）。
- 分位位置 pct_position(x) = count(v <= x) / n（经验 CDF，含 x 自身；x 为窗口最高时 = 1.0）。
- 波动率 = 日对数收益的年化标准差 sqrt(252)；跳过 > 7 天的缺口对（防伪收益，长假期不产生收益）。
"""
from __future__ import annotations
import math
from datetime import date, timedelta
from typing import Dict, List, Optional

from iris.core.models import PricePoint

TRADING_DAYS = 252
GAP_SKIP_DAYS = 7


def _d(p: PricePoint) -> date:
    return date.fromisoformat(p.date)


def percentile_position(x: float, values: List[float]) -> Optional[float]:
    """经验 CDF 分位位置：x 在 values 中的位置（0~1）。空序列返回 None。"""
    if not values:
        return None
    return sum(1.0 for v in values if v <= x) / len(values)


def percentile_value(sorted_values: List[float], q: float) -> Optional[float]:
    """线性插值分位值（q in [0,1]），sorted_values 须升序。"""
    n = len(sorted_values)
    if n == 0:
        return None
    pos = q * (n - 1)
    lo_i = int(pos)
    hi_i = min(lo_i + 1, n - 1)
    frac = pos - lo_i
    return sorted_values[lo_i] * (1 - frac) + sorted_values[hi_i] * frac


def _calendar_window(points: List[PricePoint], asof_idx: int, lookback_days: int) -> List[PricePoint]:
    """asof 含自身往前 lookback_days 日历日的点（升序输入）。"""
    asof = _d(points[asof_idx])
    lo = asof - timedelta(days=lookback_days)
    out = []
    for p in points[:asof_idx + 1]:
        if _d(p) >= lo:
            out.append(p)
    return out


def _last_n(points: List[PricePoint], asof_idx: int, n: int) -> List[PricePoint]:
    return points[max(0, asof_idx + 1 - n):asof_idx + 1]


def describe(points: List[PricePoint], asof_idx: int = -1,
             lookbacks: tuple = (90, 365, 730), vol_window_days: int = 90,
             ma_windows: tuple = (20, 60)) -> Dict:
    """asof 截面的完整统计摘要（M2.1 主入口）。"""
    if not points:
        raise ValueError("空价格序列")
    if asof_idx < 0:
        asof_idx = len(points) - 1
    asof = _d(points[asof_idx])
    last = points[asof_idx].price
    out: Dict = {
        "asof": asof.isoformat(),
        "last_price": last,
        "lookbacks": {},
        "ma": {},
        "volatility": {},
        "trend": None,
    }
    for lb in lookbacks:
        win = _calendar_window(points, asof_idx, lb)
        vals = [p.price for p in win]
        s = sorted(vals)
        out["lookbacks"][str(lb)] = {
            "n": len(vals),
            "min": s[0] if s else None,
            "max": s[-1] if s else None,
            "mean": round(sum(vals) / len(vals), 2) if vals else None,
            "median": percentile_value(s, 0.5),
            "iqr": (percentile_value(s, 0.75) - percentile_value(s, 0.25)) if s else None,
            "pct_position": percentile_position(last, vals),
        }
    # 均线（点数窗口）
    for w in ma_windows:
        win = _last_n(points, asof_idx, w)
        if len(win) == w:
            out["ma"][str(w)] = round(sum(p.price for p in win) / w, 2)
        else:
            out["ma"][str(w)] = None
    # 波动率
    rets = daily_log_returns(points)
    vol_now, vol_series = rolling_vol(rets, asof, vol_window_days)
    out["volatility"] = {
        "window_days": vol_window_days,
        "annualized": round(vol_now, 4) if vol_now is not None else None,
        "pct_position": percentile_position(vol_now, vol_series) if vol_now is not None else None,
    }
    # 趋势：MA20 vs MA60
    m20, m60 = out["ma"].get("20"), out["ma"].get("60")
    if m20 and m60 and m60:
        out["trend"] = round((m20 - m60) / m60, 4)
    return out


def daily_log_returns(points: List[PricePoint]) -> List[tuple]:
    """[(date, r)]，r = ln(P_t / P_t-1)；>7 天缺口跳过。"""
    out = []
    for i in range(1, len(points)):
        d0, d1 = _d(points[i - 1]), _d(points[i])
        if (d1 - d0).days > GAP_SKIP_DAYS:
            continue
        p0, p1 = points[i - 1].price, points[i].price
        if p0 <= 0 or p1 <= 0:
            continue
        out.append((d1, math.log(p1 / p0)))
    return out


def rolling_vol(rets: List[tuple], asof: date, vol_window_days: int) -> tuple:
    """返回 (asof 当日年化波动率, 历史上各日年化波动率序列)。样本 < 5 时返回 (None, [])。"""
    lo = asof - timedelta(days=vol_window_days)
    series: List[float] = []
    now = None
    buf: List[float] = []
    buf_dates: List[date] = []
    for d, r in rets:
        if d > asof:                  # 无前视：asof 之后的收益不进样本/分位
            break
        buf.append(r)
        buf_dates.append(d)
        while buf_dates and (d - buf_dates[0]).days > vol_window_days:
            buf.pop(0)
            buf_dates.pop(0)
        if len(buf) >= 5:
            m = sum(buf) / len(buf)
            var = sum((x - m) ** 2 for x in buf) / (len(buf) - 1)
            v = math.sqrt(var * TRADING_DAYS)
            series.append(v)
            now = v
    return now, series

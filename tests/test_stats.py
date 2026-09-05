# -*- coding: utf-8 -*-
"""M2.1 stats 原语测试。"""
from datetime import date, timedelta

from iris.core.models import PricePoint
from iris.core.stats import (daily_log_returns, describe, percentile_position,
                             percentile_value, rolling_vol)


def _pts(prices, start="2025-01-01", step_days=1):
    d = date.fromisoformat(start)
    out = []
    for p in prices:
        out.append(PricePoint(date=d.isoformat(), price=p))
        d += timedelta(days=step_days)
    return out


def test_percentile_value_interp():
    assert percentile_value([1, 2, 3, 4], 0.5) == 2.5
    assert percentile_value([1, 2, 3, 4], 0.25) == 1.75
    assert percentile_value([], 0.5) is None


def test_percentile_position():
    assert percentile_position(3, [1, 2, 3, 4]) == 0.75
    assert percentile_position(10, [1, 2, 3]) == 1.0
    assert percentile_position(1, [2, 3]) == 0.0
    assert percentile_position(1, []) is None


def test_constant_price_vol_zero():
    pts = _pts([1000] * 120)
    d = describe(pts)
    assert d["volatility"]["annualized"] == 0.0
    assert d["last_price"] == 1000
    for lb in ("90", "365", "730"):
        assert d["lookbacks"][lb]["min"] == d["lookbacks"][lb]["max"] == 1000


def test_rising_series():
    pts = _pts(list(range(500, 560)))   # 500..559 连续 60 天
    d = describe(pts)
    assert d["lookbacks"]["90"]["pct_position"] == 1.0
    assert d["lookbacks"]["90"]["min"] == 500
    assert d["lookbacks"]["90"]["max"] == 559
    assert d["ma"]["20"] == 549.5      # 最后 20 点 540..559 均值
    assert d["ma"]["60"] == 529.5


def test_ma_insufficient():
    pts = _pts([100] * 10)
    d = describe(pts)
    assert d["ma"]["60"] is None
    assert d["ma"]["20"] is None


def test_calendar_window_gap():
    # 序列中间缺 30 天（step_days=30 跳一天），365 窗口只含近期点
    pts = _pts([1000] * 20, step_days=14)   # 20 点 × 14 天
    d = describe(pts)
    assert d["lookbacks"]["90"]["n"] <= 7   # 90 天内至多 ~7 点
    assert d["lookbacks"]["90"]["min"] == 1000


def test_daily_log_returns_skips_big_gap():
    pts = _pts([1000, 1000, 1000], step_days=10)  # 间隔 10 天 > 7 -> 跳过
    assert daily_log_returns(pts) == []
    pts2 = _pts([1000, 1100, 1210])
    rs = daily_log_returns(pts2)
    assert len(rs) == 2
    assert abs(rs[0][1] - 0.0953) < 1e-3


def test_describe_fields():
    pts = _pts([1000] * 120)
    d = describe(pts)
    assert set(["asof", "last_price", "lookbacks", "ma", "volatility", "trend"]) <= set(d)
    assert d["trend"] == 0.0


def test_rolling_vol_no_lookahead():
    """asof 之后的收益不得进入 volatility（前视回归，M7.1 修复）。
    前半段低波动、asof 之后高波动：用 asof_idx 调用须与截断调用一致。"""
    base = [1000] * 200
    pts = _pts(base)                       # 200 天平稳
    pts2 = pts + _pts([1400 + (i % 5) * 40 for i in range(120)], start=(date.fromisoformat(pts[-1].date) + timedelta(days=1)).isoformat())
    i = len(pts) - 1                       # asof = 平稳段末尾
    d_cut = describe(pts2[:i + 1])
    d_idx = describe(pts2, asof_idx=i)
    assert d_idx["volatility"] == d_cut["volatility"], "asof_idx 路径混入未来收益"
    # 前视修复前：asof 之后的高波动会把 annualized 从 0 拉高到 ~0.56

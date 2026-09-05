# -*- coding: utf-8 -*-
"""M2.3 P1 历史模拟测试：结构 / 单调性 / 小样本降级 / 无前视回归。"""
import random
from datetime import date, timedelta

from iris.core.models import PricePoint
from iris.core.p1 import forecast_windows, p1_forecast, wilson_ci


def _pts(prices, start="2024-01-01"):
    d = date.fromisoformat(start)
    out = []
    for p in prices:
        out.append(PricePoint(date=d.isoformat(), price=p))
        d += timedelta(days=1)
    return out


def test_wilson_ci():
    lo, hi = wilson_ci(0, 30)
    assert lo == 0.0 and hi > 0.0
    lo2, hi2 = wilson_ci(30, 30)
    assert hi2 == 1.0 and lo2 < 1.0


def test_random_walk_structure():
    rng = random.Random(7)
    px = []
    p = 500.0
    for _ in range(1000):
        p = max(100, p * (1 + rng.gauss(0, 0.008)))
        px.append(int(round(p)))
    pts = _pts(px)
    fc = p1_forecast(pts, window_days=60, drop=0.05)
    for k in ("window_days", "drop", "n", "confidence", "method", "direction", "bucket", "percentile_position"):
        assert k in fc, "缺字段 %s" % k
    assert fc["n_sufficient"] == (fc["confidence"] == "sufficient")


def test_drop_monotonic():
    rng = random.Random(11)
    px = []
    p = 500.0
    for _ in range(1000):
        p = max(100, p * (1 + rng.gauss(0, 0.008)))
        px.append(int(round(p)))
    pts = _pts(px)
    f_easy = p1_forecast(pts, window_days=60, drop=0.01)
    f_hard = p1_forecast(pts, window_days=60, drop=0.30)
    if f_easy["confidence"] == "sufficient" and f_hard["confidence"] == "sufficient":
        assert f_easy["probability"] >= f_hard["probability"]
    else:
        # 至少结构成立（小样本也给方向字段）
        assert f_easy["confidence"] in ("sufficient", "insufficient")


def test_small_sample_degrades():
    pts = _pts([500] * 140)   # 历史很短（120 天最小历史 + 窗）
    fc = p1_forecast(pts, window_days=60, drop=0.05)
    assert fc["confidence"] == "insufficient"
    assert fc["probability"] is None
    assert fc["direction"] in ("down", "up", "flat", "unknown")


def test_no_lookahead_regression():
    """asof 之后立刻暴跌，历史全是平台 —— 正确实现看不到未来，p=0。"""
    pts = _pts([1000] * 100 + [700] * 100)
    fc = p1_forecast(pts, asof_idx=99, window_days=60, drop=0.05)
    if fc["confidence"] == "sufficient":
        assert fc["probability"] == 0.0
    else:
        # 结构上仍不允许给出正概率
        assert fc["probability"] is None


def test_forecast_windows_has_main_60():
    pts = _pts([500] * 400)
    res = forecast_windows(pts)
    assert set(res) == {"30", "60", "180"}
    assert res["60"]["window_days"] == 60

def test_wait_stats_present_on_sufficient():
    """M5 输入：周期性坑（每 40 天一个 -6% 坑）-> 匹配窗口充足，wait_stats 可解释。"""
    px = []
    for cyc in range(80):
        px.extend([1000] * 19 + [940])
    px.extend([1000] * 20)          # asof 回到平台 1000（当前价位），坑在 60 天内可及
    pts = _pts(px, start="2024-01-01")
    fc = p1_forecast(pts, window_days=60, drop=0.05)
    assert fc["confidence"] == "sufficient"
    ws = fc["wait_stats"]
    assert ws is not None and ws["n_windows"] == fc["n"]
    assert ws["n_windows"] >= 30
    assert 5.5 < ws["saving_pct"] < 6.5          # 每 60 天内必有 -6% 坑
    assert ws["loss_pct"] == 0.0                 # 无上涨窗口
    assert abs(ws["net_pct"] - ws["saving_pct"]) < 1e-9


def test_wait_stats_none_when_no_candidates():
    pts = _pts([500] * 60)
    fc = p1_forecast(pts, window_days=60, drop=0.05)
    assert "wait_stats" in fc
    assert fc["wait_stats"] is None

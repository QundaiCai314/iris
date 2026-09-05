# -*- coding: utf-8 -*-
"""M2.4 校准模块测试。"""
import random
from datetime import date, timedelta

from iris.core.calib import MAX_DEV, collect_pairs, reliability, run_report
from iris.core.models import PricePoint


def _pts(prices, start="2024-01-01"):
    d = date.fromisoformat(start)
    out = []
    for p in prices:
        out.append(PricePoint(date=d.isoformat(), price=p))
        d += timedelta(days=1)
    return out


def test_reliability_perfect():
    # 每箱 avg_p == 实际频率 -> dev=0；brier = 0.25
    pairs = [(0.5, 1)] * 5 + [(0.5, 0)] * 5 + [(0.5, 1)] * 5 + [(0.5, 0)] * 5
    rep = reliability(pairs, nbins=2)
    assert rep["max_dev"] == 0.0
    assert rep["degraded"] is False
    assert rep["brier"] == 0.25


def test_reliability_overconfident_degrade():
    # 报 0.9 但实际只有 0.1 发生 -> 高估 -> 降级
    pairs = [(0.9, 0)] * 10 + [(0.9, 1)] * 1
    rep = reliability(pairs, nbins=1)
    assert rep["max_dev"] is not None and abs(rep["max_dev"]) > MAX_DEV
    assert rep["degraded"] is True


def test_collect_pairs_no_lookahead_bounds():
    rng = random.Random(3)
    px, p = [], 500.0
    for _ in range(900):
        p = max(100, p * (1 + rng.gauss(0, 0.007)))
        px.append(int(round(p)))
    pts = _pts(px)
    pairs, notes = collect_pairs(pts)
    assert all(0.0 <= p <= 1.0 and o in (0, 1) for p, o in pairs)


def test_run_report_structure():
    pts = _pts([500] * 600)
    rep = run_report(pts, label="x")
    assert rep["label"] == "x"
    assert "rule" in rep
    assert rep["n"] >= 0

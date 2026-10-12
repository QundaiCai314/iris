# -*- coding: utf-8 -*-
"""金融计量经济学与前景理论单元测试（Ornstein-Uhlenbeck 均值回归与前景理论主观效用）。"""
from iris.core.econometrics import (
    cumulative_prospect_theory_valuation,
    fit_ornstein_uhlenbeck,
)
from iris.core.models import PricePoint


def _make_pts(prices, start="2026-01-01"):
    from datetime import date, timedelta
    d0 = date.fromisoformat(start)
    return [PricePoint(date=(d0 + timedelta(days=i)).isoformat(), price=int(p)) for i, p in enumerate(prices)]


def test_fit_ornstein_uhlenbeck_mean_reverting():
    # 构造强均值回归序列（围绕 5000 震荡）
    base = 5000
    prices = []
    p = 5800  # 起始高位
    for _ in range(60):
        p = p + 0.15 * (base - p)  # 均值回归
        prices.append(p)
    pts = _make_pts(prices)

    res = fit_ornstein_uhlenbeck(pts)
    assert res["is_mean_reverting"] is True
    assert res["half_life_days"] is not None
    assert res["half_life_days"] > 0
    assert abs(res["equilibrium_price"] - base) < 200
    assert "Vasicek" in res["citation"]


def test_fit_ornstein_uhlenbeck_short_sample():
    pts = _make_pts([1000] * 5)
    res = fit_ornstein_uhlenbeck(pts)
    assert res["is_mean_reverting"] is False
    assert res["regime"] == "insufficient_data"


def test_cumulative_prospect_theory_loss_aversion_wedge():
    # 比较客观期望与前景理论：
    # 期望省 1000 元（概率 60%），期望亏 800 元（概率 40%）
    # 客观 EV = 0.6 * 1000 - 0.4 * 800 = 600 - 320 = +280 元
    # 但在损失厌恶 lambda = 2.25 下，亏损权重放大，主观效用被显著折价
    res = cumulative_prospect_theory_valuation(
        saving_yuan=1000.0,
        loss_yuan=800.0,
        p_save=0.6,
        p_loss=0.4,
        lambda_param=2.25,
    )
    assert res["loss_aversion_ratio"] == 2.25
    assert res["objective_expected_yuan"] == 280
    assert res["loss_aversion_wedge_yuan"] > 0
    assert "损失厌恶" in res["behavior_advice"]


def test_cumulative_prospect_theory_strong_gain():
    # 极高概率省钱，极低损失
    res = cumulative_prospect_theory_valuation(
        saving_yuan=1500.0,
        loss_yuan=50.0,
        p_save=0.9,
        p_loss=0.1,
    )
    assert res["certainty_equivalent_yuan"] > 0
    assert res["prospect_value"] > 0
    assert "理性心理支持继续等待" in res["behavior_advice"]

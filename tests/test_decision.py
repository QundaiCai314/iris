# -*- coding: utf-8 -*-
"""M5.1-M5.4 决策引擎测试：分解数学 / 三色裁决 / P2 / 条件句红线。"""
from iris.core.decision import (A_WARM_PCT, BANNED_WORDS, build_conditions,
                                build_decision, decide, decompose,
                                p2_probability, traffic_light,
                                usage_loss_monthly_pct, wait_window_days)


def _fc(price=1000.0, saving=6.0, loss=1.0, n=40, min_n=30, window=60):
    return {"window_days": window, "last_price": price, "n": n, "min_n": min_n,
            "n_sufficient": n >= min_n,
            "confidence": "sufficient" if n >= min_n else "insufficient",
            "direction": "down",
            "wait_stats": {"n_windows": n, "saving_pct": saving,
                           "loss_pct": loss, "net_pct": saving - loss}}


def _fcs(s30=6.0, l30=1.0, s60=6.0, l60=1.0, price=1000.0, n=40):
    return {"30": _fc(price, s30, l30, n, window=30),
            "60": _fc(price, s60, l60, n, window=60),
            "180": _fc(price, s60 + 4, l60, n, window=180)}


def _profile(**over):
    base = {"necessity": "optional", "deadline": "none",
            "usage_intensity": "medium", "hedonic": "hedonic",
            "wait_tier": "mid", "price_view": "stable",
            "supply_news": "no", "alt_acceptable": "yes"}
    base.update(over)
    return base


def _close(a, b, eps=1e-6):
    return abs(a - b) < eps


def test_wait_window_mapping():
    assert wait_window_days({"deadline": "now"}) == 0
    assert wait_window_days({"deadline": "within_30"}) == 30
    assert wait_window_days({"deadline": "within_90"}) == 60
    assert wait_window_days({"deadline": "none"}) == 60


def test_usage_loss_monthly_pct_math():
    # A1/A2：medium 2.0 x hedonic 1.6 x mid 1.2 = 3.84 %/月
    assert _close(usage_loss_monthly_pct(_profile()), 3.84)
    assert _close(usage_loss_monthly_pct(
        _profile(usage_intensity="rarely", hedonic="utilitarian",
                 wait_tier="high")), 0.5 * 1.0 * 0.8)


def test_decompose_math():
    p = _profile()                       # u 月 3.84% -> 60 天 = 7.569...
    d = decompose(p, _fc(saving=6.0, loss=1.0), vol_pct=0.5)
    assert d["wait_days"] == 60
    assert _close(d["u_pct"], round(3.84 * 60 / 30.44, 4), 1e-9)
    assert _close(d["saving_pct"], 6.0) and _close(d["loss_history_pct"], 1.0)
    assert _close(d["buffer_pct"], 2.0)          # 2.0 x (0.5+0.5)
    assert _close(d["r_pct"], 1.0)
    assert _close(d["net_pct"], round(6.0 - 3.84 * 60 / 30.44 - 1.0 - 2.0, 4), 1e-9)
    d2 = decompose(p, _fc(saving=6.0, loss=1.0), vol_pct=0.9, supply_on=True)
    assert _close(d2["buffer_pct"], 2.8)         # 2.0 x (0.5+0.9)
    assert _close(d2["r_pct"], 2.0)              # 1.0 历史 + 1.0 供需附加


def test_gate_essential_buy():
    p = _profile(necessity="essential", deadline="within_30")
    d = decide(p, _fcs(), 0.5)
    assert d["recommendation"] == "buy" and d["traffic_light"] == "green"
    assert d["mode"] == "essential" and d["decomposition"] is None


def test_gate_deadline_now_buy():
    p = _profile(deadline="now")
    d = decide(p, _fcs(), 0.5)
    assert d["recommendation"] == "buy" and d["mode"] == "deadline_now"


def test_wait_when_saving_large_and_can_wait():
    # rarely/utilitarian/high：等 60 天 U 很小；历史省 10% -> 净期望为正 -> 等（红灯）
    p = _profile(usage_intensity="rarely", hedonic="utilitarian", wait_tier="high",
                 deadline="none")
    d = decide(p, _fcs(s60=10.0, l60=0.0), 0.5)
    assert d["recommendation"] == "wait"
    assert d["traffic_light"] == "red"
    assert d["decomposition"]["net_pct"] > 0
    assert d["decomposition"]["net_pct"] >= A_WARM_PCT


def test_buy_when_wait_not_pay():
    p = _profile(usage_intensity="high", hedonic="hedonic", wait_tier="low")
    d = decide(p, _fcs(s60=1.0, l60=0.0), 0.5)   # U 大而节省小 -> 买
    assert d["recommendation"] == "buy"
    assert d["traffic_light"] == "green"


def test_switch_when_alt_significantly_better():
    alt = {"row_type": "same_product", "satisfies_need": True,
           "saving_pct": 12.0, "saving_abs": 120, "price": 880,
           "bench_ratio": 1.0, "label": "MSI 同型号", "sku_id": "s2"}
    p = _profile(alt_acceptable="no")            # 只接受全新同款：同型号仍可换
    d = decide(p, _fcs(s60=2.0, l60=0.0), 0.5, best_alt=alt)
    assert d["recommendation"] == "switch"
    assert d["traffic_light"] == "yellow"
    assert d["switch_to"]["sku_id"] == "s2"


def test_switch_rejected_when_below_threshold_or_unacceptable():
    small = {"row_type": "same_product", "satisfies_need": True,
             "saving_pct": 4.0, "saving_abs": 40, "price": 960,
             "bench_ratio": 1.0, "label": "x", "sku_id": "s2"}
    p = _profile()
    assert decide(p, _fcs(s60=1.0, l60=0.0), 0.5, best_alt=small)["recommendation"] == "buy"
    down = {"row_type": "substitute", "satisfies_need": False,
            "saving_pct": 20.0, "saving_abs": 200, "price": 800,
            "bench_ratio": 0.6, "label": "y", "sku_id": "s3"}
    assert decide(p, _fcs(s60=1.0, l60=0.0), 0.5, best_alt=down)["recommendation"] == "buy"


def test_low_sample_never_red():
    p = _profile(usage_intensity="rarely", hedonic="utilitarian", wait_tier="high")
    fc = _fcs(s60=10.0, l60=0.0, n=12)
    d = decide(p, fc, 0.5)
    assert d["recommendation"] == "wait"
    assert d["confidence"] == "low"
    assert d["traffic_light"] == "yellow"        # 低置信只黄不红


def test_traffic_light_mapping():
    assert traffic_light("buy", -5.0) == "green"
    assert traffic_light("switch", 0.0) == "yellow"
    assert traffic_light("wait", 1.0) == "yellow"
    assert traffic_light("wait", A_WARM_PCT + 1, "sufficient") == "red"
    assert traffic_light("wait", A_WARM_PCT + 1, "low") == "yellow"


def test_p2_essential_is_one():
    p = _profile(necessity="essential")
    r = p2_probability(p, _fcs(), 0.5)
    assert r["probability"] == 1.0 and r["method"] == "gate-not-timing"


def test_p2_low_when_wait_dominates():
    # 无期限 + 等待节省大 + 低效用损失 -> 各扰动情景多判「等」-> P2 低
    p = _profile(usage_intensity="rarely", hedonic="utilitarian",
                 wait_tier="high", deadline="none", price_view="down")
    r = p2_probability(p, _fcs(s30=9.0, l30=0.0, s60=10.0, l60=0.0), 0.5)
    assert r["probability"] < 0.4
    assert r["n_scenarios"] >= 18
    assert set(r["dimensions"]) == {"wait_tier_mult", "wait_days", "vol_pct",
                                    "price_view_factor", "supply_premium_pct"}


def test_p2_high_when_buy_dominates():
    # 高频重度使用 + 享乐 + 可等档位低：U 大、节省小 -> 各情景多判「买」
    p = _profile(usage_intensity="high", hedonic="hedonic", wait_tier="low",
                 deadline="none", price_view="up")
    r = p2_probability(p, _fcs(s30=1.0, l30=0.0, s60=1.5, l60=0.0), 0.5,
                       supply_on=True)
    assert r["probability"] >= 0.8


def test_conditions_change_with_deadline():
    up = build_decision(_profile(usage_intensity="rarely", hedonic="utilitarian",
                                 wait_tier="high", deadline="within_30",
                                 supply_news="no"),
                        _fcs(s60=10.0, l60=0.0), 0.5)
    low = build_decision(_profile(usage_intensity="rarely", hedonic="utilitarian",
                                  wait_tier="high", deadline="none",
                                  supply_news="no"),
                         _fcs(s60=10.0, l60=0.0), 0.5)
    t1 = [c["text"] for c in up["conditions"]]
    t2 = [c["text"] for c in low["conditions"]]
    assert t1 != t2
    assert any("30 天内" in t for t in t1) and any("不急着用" in t for t in t2)


def test_conditions_banned_words_and_promo():
    evs = [{"type": "promo", "date": "2026-11-11", "days_ahead": 69,
            "beyond_days": 9, "summary_text": "历史窗口均值约 -3%（n=3，仅量级参考）"}]
    p = _profile(usage_intensity="rarely", hedonic="utilitarian",
                 wait_tier="high", deadline="none", supply_news="yes")
    d = build_decision(p, _fcs(s60=10.0, l60=0.0), 0.5, upcoming=evs)
    texts = [c["text"] for c in d["conditions"]]
    assert texts
    for banned in BANNED_WORDS:
        for t in texts:
            assert banned not in t, "%s in %s" % (banned, t)
    assert any("2026-11-11" in t for t in texts)
    assert any("供需" in t or "缺货" in t for t in texts)


def test_build_decision_switches_with_alt():
    alt = {"row_type": "same_product", "satisfies_need": True,
           "saving_pct": 15.0, "saving_abs": 150, "price": 850,
           "bench_ratio": 0.98, "label": "MSI VENTUS", "sku_id": "s2"}
    d = build_decision(_profile(usage_intensity="high", deadline="within_30",
                                alt_acceptable="no"),
                       _fcs(s60=1.0, l60=0.0), 0.5, best_alt=alt)
    assert d["recommendation"] == "switch"
    assert d["switch_to"]["sku_id"] == "s2"
    assert any(c["scenario"] == "switch" for c in d["conditions"])

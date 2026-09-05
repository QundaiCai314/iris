# -*- coding: utf-8 -*-
"""M10 行为提示层测试：确定性规则 / 不改裁决 / 红线词扫描 / 管线挂载。"""
from iris.agent import pipeline
from iris.core.behavior import (HIGH_POS_THRESHOLD, RERUN_ANXIETY_MIN,
                                build_behavior_hints)
from iris.core.decision import BANNED_WORDS


def _rules(card, **kw):
    return [h["rule"] for h in build_behavior_hints(card, **kw)]


def test_pipeline_mounts_behavior_hints():
    card = pipeline.build_card(dict(pipeline.SCENARIOS[0]["profile"]),
                               "rtx5070-gigabyte-mid-pdd",
                               just_resolved=True)
    assert isinstance(card["behavior_hints"], list)
    rules = [h["rule"] for h in card["behavior_hints"]]
    assert "high_percentile_rally" in rules
    assert "fresh_card" in rules          # just_resolved=True 且首次出卡
    for h in card["behavior_hints"]:
        for w in BANNED_WORDS:
            assert w not in h["text"]


def test_fresh_card_only_on_first_resolve():
    card = pipeline.build_card(dict(pipeline.SCENARIOS[0]["profile"]),
                               "rtx5070-gigabyte-mid-pdd", just_resolved=True)
    assert "fresh_card" in _rules(card, just_resolved=True)
    assert "fresh_card" not in _rules(card, just_resolved=True, rerun_count=1)
    assert "fresh_card" not in _rules(card, rerun_count=2)


def test_rerun_anxiety_threshold():
    card = pipeline.build_card(dict(pipeline.SCENARIOS[0]["profile"]),
                               "rtx5070-gigabyte-mid-pdd", just_resolved=True)
    assert "rerun_anxiety" not in _rules(card, rerun_count=RERUN_ANXIETY_MIN - 1)
    assert "rerun_anxiety" in _rules(card, rerun_count=RERUN_ANXIETY_MIN)


def test_hints_do_not_touch_decision():
    p = dict(pipeline.SCENARIOS[0]["profile"])
    c0 = pipeline.build_card(p, "rtx5070-gigabyte-mid-pdd")
    c1 = pipeline.build_card(p, "rtx5070-gigabyte-mid-pdd",
                             rerun_count=5, just_resolved=True)
    assert c0["decision"] == c1["decision"]
    assert c0["p1"] == c1["p1"]


def test_rules_are_deterministic():
    p = dict(pipeline.SCENARIOS[0]["profile"])
    a = pipeline.build_card(p, "rtx5070-gigabyte-mid-pdd",
                            rerun_count=4, just_resolved=True)
    b = pipeline.build_card(p, "rtx5070-gigabyte-mid-pdd",
                            rerun_count=4, just_resolved=True)
    assert a["behavior_hints"] == b["behavior_hints"]


def test_promo_halo_needs_buy():
    """promo_halo 只在裁决为 buy 且 30 天内有大促时出现（构造输入验证门槛）。"""
    card = pipeline.build_card(dict(pipeline.SCENARIOS[0]["profile"]),
                               "rtx5080-asus-tuf-mid")
    fake = dict(card)
    fake["events"] = dict(card.get("events") or {})
    fake["events"]["upcoming"] = [
        {"type": "promo", "title": "双11", "date": "2026-11-11",
         "days_ahead": 20, "beyond_days": 0, "confidence": "high"}]
    # 该 SKU 首画像裁决为 switch -> 不触发
    assert "promo_halo" not in _rules(fake)
    # 同输入 + buy 裁决 -> 触发
    fake["decision"] = dict(card["decision"], recommendation="buy")
    assert "promo_halo" in _rules(fake)


def test_high_percentile_threshold():
    """分位低于阈值不触发高位反弹提示。"""
    card = pipeline.build_card(dict(pipeline.SCENARIOS[0]["profile"]),
                               "rtx5080-asus-tuf-mid")
    fake = dict(card)
    fake["stats"] = dict(card["stats"])
    fake["stats"]["lookbacks"] = dict(card["stats"]["lookbacks"])
    fake["stats"]["lookbacks"]["90"] = dict(
        card["stats"]["lookbacks"]["90"], pct_position=HIGH_POS_THRESHOLD - 0.05)
    assert "high_percentile_rally" not in _rules(fake)

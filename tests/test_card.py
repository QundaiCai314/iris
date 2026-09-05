# -*- coding: utf-8 -*-
"""M2.5 决策卡结构与校验测试。"""
from iris.core.card import build_card, validate_card


def _stats():
    return {"asof": "2026-09-03", "last_price": 8789,
            "lookbacks": {"90": {"pct_position": 0.9}, "365": {"pct_position": 0.75}},
            "ma": {"20": 8500, "60": 8200}, "volatility": {"annualized": 0.12, "pct_position": 0.6},
            "trend": 0.02}


def _p1_ok():
    return {"30": {"window_days": 30, "drop": 0.05, "n": 40, "confidence": "sufficient",
                   "method": "v1-history-frequency", "method_note": "", "direction": "down",
                   "probability": 0.3, "ci95": [0.1, 0.5], "hits": 12},
            "60": {"window_days": 60, "drop": 0.05, "n": 40, "confidence": "sufficient",
                   "method": "v1-history-frequency", "method_note": "", "direction": "down",
                   "probability": 0.4, "ci95": [0.2, 0.6], "hits": 16},
            "180": {"window_days": 180, "drop": 0.05, "n": 40, "confidence": "sufficient",
                    "method": "v1-history-frequency", "method_note": "", "direction": "down",
                    "probability": 0.5, "ci95": [0.3, 0.7], "hits": 20}}


def test_card_roundtrip_ok():
    card = build_card("rtx5080", "rtx5080-asus-tuf-mid", "2026-09-03", _stats(), _p1_ok())
    assert validate_card(card) == []


def test_card_missing_meta():
    card = build_card("rtx5080", "rtx5080-asus-tuf-mid", "2026-09-03", _stats(), _p1_ok())
    del card["meta"]["engine_version"]
    errs = validate_card(card)
    assert any("engine_version" in e for e in errs)


def test_card_insufficient_ok_without_probability():
    p1 = {"60": {"window_days": 60, "drop": 0.05, "n": 5, "confidence": "insufficient",
                 "method": "v1-history-frequency", "method_note": "", "direction": "flat",
                 "median_future_low": 8700, "low_q25": 8600},
          "30": {"window_days": 30, "drop": 0.05, "n": 5, "confidence": "insufficient",
                 "method": "v1-history-frequency", "method_note": "", "direction": "flat"},
          "180": {"window_days": 180, "drop": 0.05, "n": 5, "confidence": "insufficient",
                  "method": "v1-history-frequency", "method_note": "", "direction": "flat"}}
    card = build_card("p", "s", "2026-09-03", _stats(), p1)
    assert validate_card(card) == []


def test_card_sufficient_requires_probability():
    p1 = _p1_ok()
    del p1["60"]["probability"]
    card = build_card("rtx5080", "rtx5080-asus-tuf-mid", "2026-09-03", _stats(), p1)
    errs = validate_card(card)
    assert any("probability" in e for e in errs)

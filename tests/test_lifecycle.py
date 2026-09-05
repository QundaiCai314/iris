# -*- coding: utf-8 -*-
"""M3.2 生命周期代理测试。"""
import os

import pytest

from iris.core.lifecycle import DEFAULT_DIR, expect_price, list_families, load_family, pct_at_month


def test_families_exist():
    fams = list_families()
    assert set(fams) >= {"gpu", "phone", "laptop", "console", "home"}


def test_gpu_interp():
    fam = load_family("gpu")
    assert fam["source_note"]
    assert pct_at_month(fam, 0) == 1.0
    p6 = pct_at_month(fam, 6)
    assert 0.75 < p6 < 0.90          # 半年 -10%~-25% 量级
    p12 = pct_at_month(fam, 12)
    assert p12 < p6                   # 越久越低
    assert pct_at_month(fam, 999) == fam["curve"][-1][1]  # clamp


def test_phone_source_anchor():
    fam = load_family("phone")
    assert abs(pct_at_month(fam, 5) - 0.89) < 0.01   # 学术实证锚点
    assert abs(pct_at_month(fam, 24) - 0.47) < 0.01


def test_missing_family_raises():
    with pytest.raises(FileNotFoundError):
        load_family("no-such-family")


def test_expect_price_proxy_label():
    r = expect_price(8000, "2026-10-01", "2026-12-01", "gpu")
    assert r["proxy"] is True
    assert 0 < r["expect_price"] < 8000
    assert "months_since_launch" in r and abs(r["months_since_launch"] - 2.0) < 0.2

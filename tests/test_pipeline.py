# -*- coding: utf-8 -*-
"""M6 管线回归：解析匹配 / 出卡完整性 / 演示场景覆盖。"""
from iris.agent import pipeline


def test_resolve_gpu_url():
    r = pipeline.resolve_product("https://item.jd.com/10086.html 华硕 RTX 5080 TUF 显卡 16G")
    assert r["product"]["category"] == "显卡"
    assert r["sku_id"] == "rtx5080-asus-tuf-mid"
    assert r["catalog_hit"] is True


def test_resolve_5070ti_before_5070():
    r = pipeline.resolve_product("RTX 5070 Ti 微星 显卡")
    assert r["sku_id"] and "5070ti" in r["sku_id"]


def test_resolve_unknown_keeps_manual_path():
    r = pipeline.resolve_product("今天天气不错想买个东西")
    assert r["product"]["category"] is None
    assert r["sku_id"] is None and r["catalog_hit"] is False


def test_build_card_full_fields():
    c = pipeline.build_card(dict(pipeline.SCENARIOS[0]["profile"]),
                            "rtx5080-asus-tuf-mid")
    for k in ("meta", "stats", "p1", "events", "alternatives", "decision",
              "evidence", "kline"):
        assert k in c, "缺字段 %s" % k
    assert c["meta"]["engine_version"] == "0.3.0"
    assert c["decision"]["p2"]["n_scenarios"] >= 18
    assert c["events"]["upcoming"]
    assert c["alternatives"]["rows"]
    assert c["evidence"] and c["kline"][-1]["date"] == c["stats"]["asof"]


def test_scenarios_sku_exist():
    d = pipeline.load_demo()
    for s in pipeline.SCENARIOS:
        assert s["sku"] in d["skus"]
        assert s["profile"]["category"] == "显卡"
        assert s["profile"]["purpose"]


def test_resolve_real_products():
    r1 = pipeline.resolve_product("Apple iPhone 15 Pro 256G 黑色钛金属 手机")
    assert r1["product"]["category"] == "手机"
    assert r1["sku_id"] == "iphone15pro-256g-jd"
    assert r1["catalog_hit"] is True

    r2 = pipeline.resolve_product("华硕 TUF GeForce RTX 4080 16GB GAMING 显卡")
    assert r2["product"]["category"] == "显卡"
    assert r2["sku_id"] == "rtx4080-asus-tuf-jd"
    assert r2["catalog_hit"] is True

    r3 = pipeline.resolve_product("索尼 PlayStation 5 国行光驱版 游戏主机")
    assert r3["product"]["category"] == "游戏机"
    assert r3["sku_id"] == "ps5-disc-drive-jd"
    assert r3["catalog_hit"] is True


def test_build_card_real_products():
    c = pipeline.build_card({"name": "iPhone 15 Pro", "category": "手机", "purpose": "日常通讯", "wait_tier": "mid"},
                            "iphone15pro-256g-jd")
    assert c["meta"]["sku_id"] == "iphone15pro-256g-jd"
    assert c["decision"]["recommendation"] in ("buy", "wait", "switch")
    assert any("real-market-archive" in ev["ref"] for ev in c["evidence"])

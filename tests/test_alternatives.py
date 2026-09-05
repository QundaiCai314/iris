# -*- coding: utf-8 -*-
"""M5.3 替代品矩阵测试（R03 降级版）：配对 / 性能对齐 / 换购门槛 / 措辞红线。"""
from iris.core.alternatives import (NEED_BENCH_RATIO, best_switch, build_rows,
                                    need_bench_ratio)
from iris.core.models import Product, Sku, SkuAttributes


def _p(pid, name="RTX 5080", cat="显卡"):
    return Product(product_id=pid, name=name, category=cat,
                   launch_date="2025-01-01", lifecycle_family="gpu")


def _s(sid, pid, bench, brand="asus", tier="mid", channel="jd",
       cooling="3fan", warranty=3):
    return Sku(sku_id=sid, product_id=pid, brand=brand, tier=tier,
               channel=channel,
               attributes=SkuAttributes(vram_gb=0, tdp_w=0, cooling=cooling,
                                        warranty_years=warranty, benchmark=bench),
               launch_price=0)


def _world():
    products = {"p5080": _p("p5080"), "p5070ti": _p("p5070ti", "RTX 5070 Ti"),
                "p5070": _p("p5070", "RTX 5070")}
    skus = {
        "asus-mid": _s("asus-mid", "p5080", 100.0, brand="asus"),
        "msi-entry": _s("msi-entry", "p5080", 96.0, brand="msi", tier="entry",
                        cooling="2fan"),
        "colorful-high": _s("colorful-high", "p5080", 103.0, brand="colorful",
                            tier="high"),
        "5070ti-mid": _s("5070ti-mid", "p5070ti", 85.0, brand="msi"),
        "5070-mid": _s("5070-mid", "p5070", 70.0, brand="gigabyte"),
    }
    prices = {"asus-mid": 9000, "msi-entry": 8000, "colorful-high": 9600,
              "5070ti-mid": 6500, "5070-mid": 4000}
    return products, skus, prices


def test_need_bench_ratio_lines():
    assert NEED_BENCH_RATIO["游戏"] == 0.75
    assert need_bench_ratio("AI / 跑模型") == 0.85
    assert need_bench_ratio("编程 / 日常") == 0.6
    assert need_bench_ratio(None) == 0.6


def test_rows_same_product_math():
    products, skus, prices = _world()
    mx = build_rows("asus-mid", products, skus, prices, purpose="游戏")
    by_id = {r["sku_id"]: r for r in mx["rows"]}
    assert mx["target"]["price"] == 9000
    m = by_id["msi-entry"]
    assert m["row_type"] == "same_product"
    assert m["saving_abs"] == 1000 and m["saving_pct"] == 11.11
    assert m["satisfies_need"] is True
    # 换品牌措辞：不替用户裁决
    assert "值不值由你判断" in m["note"]
    c = by_id["colorful-high"]
    assert c["saving_abs"] == -600 and c["diff_pct"] == 6.67


def test_cross_product_per_yuan_alignment():
    products, skus, prices = _world()
    mx = build_rows("asus-mid", products, skus, prices, purpose="编程 / 日常")
    s70 = next(r for r in mx["rows"] if r["sku_id"] == "5070-mid")
    # 每元性能：目标 100/9000*1000=11.111；5070 70/4000*1000=17.5 -> 157.5%
    assert s70["satisfies_need"] is True          # 70 >= 100 x 0.6
    assert s70["bench_ratio"] == 0.7
    assert "157.5" in s70["note"]
    ti = next(r for r in mx["rows"] if r["sku_id"] == "5070ti-mid")
    assert ti["satisfies_need"] is True           # 85 >= 60


def test_satisfies_need_depends_on_purpose():
    products, skus, prices = _world()
    mx_game = build_rows("asus-mid", products, skus, prices, purpose="游戏")
    mx_light = build_rows("asus-mid", products, skus, prices, purpose="编程 / 日常")
    g70 = next(r for r in mx_game["rows"] if r["sku_id"] == "5070-mid")
    l70 = next(r for r in mx_light["rows"] if r["sku_id"] == "5070-mid")
    assert g70["satisfies_need"] is False         # 70 < 100 x 0.75
    assert l70["satisfies_need"] is True


def test_best_switch_same_product_only_when_no_alt():
    products, skus, prices = _world()
    # 只接受全新同款：跨型号不可选 -> 最佳 = msi-entry（省 11.1% >= 8%）
    b = best_switch("asus-mid", products, skus, prices,
                    purpose="游戏", alt_acceptable="no")
    assert b is not None and b["row_type"] == "same_product"
    assert b["sku_id"] == "msi-entry"
    assert "A5" in b["rule"]


def test_best_switch_with_alt_allowed():
    products, skus, prices = _world()
    # 可接受平替 + 游戏：5070ti（省 27.8%，85>=75）> msi-entry（11.1%）
    b = best_switch("asus-mid", products, skus, prices,
                    purpose="游戏", alt_acceptable="yes")
    assert b["sku_id"] == "5070ti-mid"
    # 可接受平替 + 日常需求：5070 省 55.6% 更大
    b2 = best_switch("asus-mid", products, skus, prices,
                     purpose="编程 / 日常", alt_acceptable="yes")
    assert b2["sku_id"] == "5070-mid"


def test_best_switch_none_when_no_meaningful_saving():
    products, skus, prices = _world()
    prices["msi-entry"] = 8600                 # 省 4.4% < 8%：无可换
    b = best_switch("asus-mid", products, skus, prices,
                    purpose="游戏", alt_acceptable="no")
    assert b is None

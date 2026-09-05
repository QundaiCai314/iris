# -*- coding: utf-8 -*-
"""M3.1 事件研究测试。"""
import math
from datetime import date, timedelta

from iris.core.events import (build_event_study, category_control, event_scope_match,
                              product_daily_index, relative_path, summarize)
from iris.core.models import (EventItem, PricePoint, PriceSeries, Product, Sku,
                              SkuAttributes)


def _mk_series(days, start_price, drift=0.0, start="2025-01-01"):
    """生成 {iso: price}，每日价格 = start_price * (1+drift)^k。"""
    out = {}
    d = date.fromisoformat(start)
    for k in range(days):
        out[d.isoformat()] = start_price * ((1 + drift) ** k)
        d += timedelta(days=1)
    return out


def _series_obj(d, sid="s"):
    return PriceSeries(sku_id=sid,
                       points=[PricePoint(date=k, price=round(v)) for k, v in sorted(d.items())])


def test_product_index_median():
    skus = {"a1": Sku(sku_id="a1", product_id="p", brand="x", tier="mid", channel="jd",
                       attributes=SkuAttributes()),
            "a2": Sku(sku_id="a2", product_id="p", brand="y", tier="high", channel="jd",
                       attributes=SkuAttributes())}
    by = {"a1": _series_obj({"2025-01-01": 100, "2025-01-02": 110}),
          "a2": _series_obj({"2025-01-01": 200, "2025-01-02": 190})}
    idx = product_daily_index(by, skus, "p")
    assert idx["2025-01-01"] == 150
    assert idx["2025-01-02"] == 150


def test_relative_path_control_diff():
    """事件品在事件后跌 10%，对照平稳 -> 差分路径约 -10%。"""
    ev_date = date(2025, 3, 1)
    base = date(2025, 1, 1)
    # 事件品：前 60 天 1000 平；3/1 起每日 -1%（60 天后约 -45%，取前 10 天约 -10%）
    s = {}
    c = {}
    d = base
    while d < ev_date:
        s[d.isoformat()] = 1000.0
        c[d.isoformat()] = 1000.0
        d += timedelta(days=1)
    k = 0
    while k <= 40:
        s[d.isoformat()] = 1000.0 * (0.99 ** k)
        c[d.isoformat()] = 1000.0
        d += timedelta(days=1)
        k += 1
    rp = relative_path(s, c, ev_date, before=30, after=60)
    # 事件后约 10 天（0.99^10 = 0.904）应约 -9.6%
    v10 = rp["path"].get(10)
    assert v10 is not None and abs(v10 - (-9.56)) < 1.0, v10


def test_absolute_path_when_no_control():
    s = _mk_series(120, 1000, drift=-0.01)
    rp = relative_path(s, None, date(2025, 3, 1), before=30, after=60)
    # 基线在 E-30，累积 60 天 -1%/天 ≈ 0.99^60-1
    assert rp["path"] and abs(rp["path"].get(30, 0) - (-45.3)) < 1.5


def test_summarize_pooling():
    p1 = {"path": {30: -5.0, 60: -8.0}}
    p2 = {"path": {30: -3.0, 60: -6.0}}
    s = summarize([p1, p2], 60)
    assert s["n"] == 2 and s["mean_pct"] == -7.0


def test_event_date_shift_robustness():
    """事件日错位 ±3 天：仍能检出下跌（幅度接近，容差放宽）。"""
    def make_path(ev_date):
        base = date(2025, 1, 1)
        s, c = {}, {}
        d = base
        while d < ev_date:
            s[d.isoformat()] = 1000.0
            c[d.isoformat()] = 1000.0
            d += timedelta(days=1)
        k = 0
        while k <= 40:
            s[d.isoformat()] = 1000.0 * (0.985 ** k)
            c[d.isoformat()] = 1000.0
            d += timedelta(days=1)
            k += 1
        return relative_path(s, c, ev_date, before=30, after=60)
    ev = date(2025, 3, 1)
    v0 = make_path(ev).get("path", {}).get(20)
    v1 = make_path(ev + timedelta(days=3)).get("path", {}).get(20)
    v2 = make_path(ev - timedelta(days=3)).get("path", {}).get(20)
    vals = [x for x in (v0, v1, v2) if x is not None]
    assert len(vals) == 3
    assert all(x < 0 for x in vals)           # 方向一致
    assert max(vals) - min(vals) < 4.0        # 幅度差异可控（错位 3 天）


def test_scope_match():
    assert event_scope_match(EventItem("e", "launch", "t", "2025-01-01", "all"), "p1")
    assert event_scope_match(EventItem("e", "launch", "t", "2025-01-01", "p1,p2"), "p2")
    assert not event_scope_match(EventItem("e", "launch", "t", "2025-01-01", "p2"), "p1")


def test_build_study_promo_pooling():
    """demo 数据集成（文件存在时）：5080 的 3 起 promo 事件 pooling 出 60 天 horizon。"""
    import os
    demo = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "demo")
    if not os.path.exists(os.path.join(demo, "catalog.json")):
        return  # demo 数据未生成时跳过
    from iris.core.prices import load_all, load_events
    products, skus, series = load_all(os.path.join(demo, "prices"), os.path.join(demo, "catalog.json"))
    evs = load_events(os.path.join(demo, "events.json"))
    study = build_event_study(series, skus, products, evs, "rtx5080", event_type="promo")
    h60 = study["promo"]["horizons"]["60"]
    assert h60["n"] >= 3
    assert h60["mean_pct"] is not None

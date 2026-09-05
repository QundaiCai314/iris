# -*- coding: utf-8 -*-
"""M1.3 校验器测试：schema 规则 1-8 与 resample。"""
import json
import os
from datetime import date

import pytest

from iris.core.models import EventItem, PricePoint, PriceSeries, Product, Sku, SkuAttributes
from iris.core.prices import (load_catalog, load_events, load_series_file, resample_ohlc,
                              validate_all, validate_catalog, validate_series)


def _product(pid="p1"):
    return Product(product_id=pid, name="测试卡", category="显卡",
                   launch_date="2025-01-30", lifecycle_family="gpu")


def _sku(sid="p1-a-mid", pid="p1"):
    return Sku(sku_id=sid, product_id=pid, brand="a", tier="mid", channel="jd",
               attributes=SkuAttributes(benchmark=100.0), launch_price=5000)


def _series(sid="p1-a-mid", n=60, start="2025-01-01", step=1, price=None):
    pts = []
    d = date.fromisoformat(start)
    from datetime import timedelta
    for i in range(n):
        pts.append(PricePoint(date=d.isoformat(), price=(price if price else 5000 + i)))
        d += timedelta(days=step)
    return PriceSeries(sku_id=sid, points=pts)


def _write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)


def _mk_catalog(products, skus):
    return {"products": [{"product_id": p.product_id, "name": p.name, "category": p.category,
                          "launch_date": p.launch_date, "lifecycle_family": p.lifecycle_family,
                          "status": p.status} for p in products],
            "skus": [{"sku_id": s.sku_id, "product_id": s.product_id, "brand": s.brand,
                      "tier": s.tier, "channel": s.channel,
                      "attributes": {"benchmark": s.attributes.benchmark},
                      "launch_price": s.launch_price} for s in skus]}


def test_roundtrip_ok(tmp_path):
    cat = os.path.join(tmp_path, "catalog.json")
    pdir = os.path.join(tmp_path, "prices")
    os.makedirs(pdir)
    _write_json(cat, _mk_catalog([_product()], [_sku()]))
    _write_json(os.path.join(pdir, "p1-a-mid.json"),
                {"sku_id": "p1-a-mid", "source": "manual",
                 "points": [{"date": p.date, "price": p.price} for p in _series().points]})
    products, skus = load_catalog(cat)
    ser = load_series_file(os.path.join(pdir, "p1-a-mid.json"), "p1-a-mid")
    errs, warns = validate_all(products, skus, {"p1-a-mid": ser})
    assert errs == []
    assert warns == []


def _assert_has_error(errs, keyword):
    assert any(keyword in e for e in errs), "期望含 %r 的错误，实际: %r" % (keyword, errs)


def test_price_nonpositive(tmp_path):
    ser = _series()
    ser.points[3].price = 0
    e, _ = validate_series(ser)
    _assert_has_error(e, "价格非法")


def test_negative_price(tmp_path):
    ser = _series()
    ser.points[3].price = -5
    e, _ = validate_series(ser)
    _assert_has_error(e, "价格非法")


def test_float_price(tmp_path):
    ser = _series()
    ser.points[3].price = 5000.5
    e, _ = validate_series(ser)
    _assert_has_error(e, "价格非法")


def test_date_out_of_order(tmp_path):
    ser = _series()
    ser.points[4].date = "2025-01-03"   # 乱序
    e, _ = validate_series(ser)
    _assert_has_error(e, "非严格递增")


def test_duplicate_date(tmp_path):
    ser = _series()
    ser.points[4].date = ser.points[3].date
    e, _ = validate_series(ser)
    _assert_has_error(e, "重复日期")


def test_bad_iso_date(tmp_path):
    ser = _series()
    ser.points[4].date = "2025/01/03"
    e, _ = validate_series(ser)
    _assert_has_error(e, "日期非法")


def test_too_few_points(tmp_path):
    e, _ = validate_series(_series(n=10))
    _assert_has_error(e, "点数不足")


def test_sku_orphan(tmp_path):
    products, skus = {"p1": _product()}, {"x1": _sku("x1", "ghost")}
    e = validate_catalog(products, skus)
    _assert_has_error(e, "不存在")


def test_sku_id_filename_mismatch(tmp_path):
    f = os.path.join(tmp_path, "a.json")
    _write_json(f, {"sku_id": "b", "points": []})
    with pytest.raises(ValueError):
        load_series_file(f, "a")


def test_big_gap_warns(tmp_path):
    pts = _series(n=200).points
    # 挖掉 2025-03-01 ~ 2025-06-15（>90 天）
    kept = [p for p in pts if not (date.fromisoformat("2025-03-01") <= date.fromisoformat(p.date) <= date.fromisoformat("2025-06-15"))]
    ser = PriceSeries(sku_id="p1-a-mid", points=kept)
    e, w = validate_series(ser)
    assert e == []
    assert any("大缺口" in x for x in w)


def test_resample_ohlc_weekly():
    pts = [PricePoint(date=date(2025, 1, i + 1).isoformat(), price=i + 1) for i in range(10)]
    out = resample_ohlc(pts, 7)
    assert len(out) == 2
    b0, b1 = out[0], out[1]
    assert (b0["open"], b0["high"], b0["low"], b0["close"], b0["n"]) == (1, 7, 1, 7, 7)
    assert (b1["open"], b1["high"], b1["low"], b1["close"], b1["n"]) == (8, 10, 8, 10, 3)


def test_events_load(tmp_path):
    f = os.path.join(tmp_path, "events.json")
    _write_json(f, [{"event_id": "e1", "type": "promo", "title": "618", "date": "2025-06-18"}])
    evs = load_events(f)
    assert len(evs) == 1
    assert isinstance(evs[0], EventItem)
    assert evs[0].confidence == "reported"   # 默认值

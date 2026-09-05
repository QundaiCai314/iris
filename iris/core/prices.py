# -*- coding: utf-8 -*-
"""价格序列加载与校验（M1.3；口径见 docs/data-schema.md §4-5）。纯标准库。"""
from __future__ import annotations
import json
import os
from datetime import date, datetime
from typing import Dict, List, Tuple

from iris.core.models import EventItem, PricePoint, PriceSeries, Product, Sku, SkuAttributes


# ---------- 加载 ----------

def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def load_catalog(path: str) -> Tuple[Dict[str, Product], Dict[str, Sku]]:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    products: Dict[str, Product] = {}
    for p in raw.get("products", []):
        products[p["product_id"]] = Product(
            product_id=p["product_id"], name=p["name"], category=p["category"],
            launch_date=p["launch_date"], lifecycle_family=p["lifecycle_family"],
            status=p.get("status", "active"))
    skus: Dict[str, Sku] = {}
    for s in raw.get("skus", []):
        a = s.get("attributes", {})
        skus[s["sku_id"]] = Sku(
            sku_id=s["sku_id"], product_id=s["product_id"], brand=s["brand"],
            tier=s["tier"], channel=s["channel"],
            attributes=SkuAttributes(vram_gb=a.get("vram_gb", 0), tdp_w=a.get("tdp_w", 0),
                                     cooling=a.get("cooling", ""), warranty_years=a.get("warranty_years", 0),
                                     benchmark=a.get("benchmark", 0.0)),
            launch_price=s.get("launch_price", 0))
    return products, skus


def load_series_file(path: str, sku_id: str) -> PriceSeries:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    file_sku = raw.get("sku_id", "")
    if file_sku != sku_id:
        raise ValueError("文件内 sku_id(%s) 与文件名不一致: %s" % (file_sku, sku_id))
    pts = [PricePoint(date=pp["date"], price=pp["price"], quality=pp.get("quality", "confirmed"))
           for pp in raw.get("points", [])]
    return PriceSeries(sku_id=sku_id, source=raw.get("source", "manual"), points=pts)


def load_all(prices_dir: str, catalog_path: str):
    """返回 (products, skus, series_dict)。"""
    products, skus = load_catalog(catalog_path)
    series: Dict[str, PriceSeries] = {}
    for fname in os.listdir(prices_dir):
        if fname.endswith(".json"):
            sku_id = fname[:-5]
            series[sku_id] = load_series_file(os.path.join(prices_dir, fname), sku_id)
    return products, skus, series


def load_events(path: str) -> List[EventItem]:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return [EventItem(event_id=e["event_id"], type=e["type"], title=e["title"],
                      date=e["date"], scope=e.get("scope", "all"),
                      confidence=e.get("confidence", "reported")) for e in raw]


# ---------- 校验 ----------

def validate_catalog(products: Dict[str, Product], skus: Dict[str, Sku]) -> List[str]:
    errs: List[str] = []
    seen_p, seen_s = set(), set()
    for pid, p in products.items():
        if pid in seen_p:
            errs.append("product_id 重复: %s" % pid)
        seen_p.add(pid)
        try:
            _parse_date(p.launch_date)
        except ValueError:
            errs.append("launch_date 非法 ISO 日期: %s" % p.launch_date)
    for sid, s in skus.items():
        if sid in seen_s:
            errs.append("sku_id 重复: %s" % sid)
        seen_s.add(sid)
        if s.product_id not in products:
            errs.append("SKU %s 指向不存在的 product: %s" % (sid, s.product_id))
        if s.tier not in ("entry", "mid", "high"):
            errs.append("SKU %s tier 非法: %s" % (sid, s.tier))
    return errs


def validate_series(ser: PriceSeries) -> Tuple[List[str], List[str]]:
    """返回 (errors, warnings)。errors 非空即拒绝使用。"""
    errs: List[str] = []
    warns: List[str] = []
    pts = ser.points
    if len(pts) < 30:
        errs.append("%s 点数不足: %d < 30" % (ser.sku_id, len(pts)))
    prev = None
    seen = set()
    for i, pp in enumerate(pts):
        try:
            d = _parse_date(pp.date)
        except ValueError:
            errs.append("%s 第 %d 点日期非法: %r" % (ser.sku_id, i, pp.date))
            continue
        if not isinstance(pp.price, int) or pp.price <= 0:
            errs.append("%s %s 价格非法: %r（须为正整数）" % (ser.sku_id, pp.date, pp.price))
        if pp.date in seen:
            errs.append("%s 重复日期: %s" % (ser.sku_id, pp.date))
        seen.add(pp.date)
        if prev is not None and d <= prev:
            errs.append("%s 日期非严格递增: %s" % (ser.sku_id, pp.date))
        prev = d
    if pts:
        # 大缺口警告（连续缺失 > 90 天，schema §4-8）
        gaps, cur_start = [], None
        prev_d = None
        for pp in pts:
            try:
                d = _parse_date(pp.date)
            except ValueError:
                continue  # 坏日期已在主循环报错
            if prev_d is not None:
                gap = (d - prev_d).days - 1
                if gap > 90:
                    gaps.append("%s ~ %s 缺 %d 天" % (prev_d, d, gap))
            prev_d = d
        for g in gaps[:3]:
            warns.append("%s 大缺口: %s" % (ser.sku_id, g))
        if len(gaps) > 3:
            warns.append("%s 大缺口共 %d 处" % (ser.sku_id, len(gaps)))
    return errs, warns


def validate_all(products, skus, series) -> Tuple[List[str], List[str]]:
    errs = validate_catalog(products, skus)
    warns: List[str] = []
    for sid, ser in series.items():
        if sid not in skus:
            errs.append("价格文件对应 SKU 不在 catalog: %s" % sid)
        e, w = validate_series(ser)
        errs += e
        warns += w
    return errs, warns


# ---------- 重采样 ----------

def resample_ohlc(points: List[PricePoint], freq_days: int = 7) -> List[Dict]:
    """按固定天数窗口聚合 OHLC；无点窗口跳过，不插值（总纲 2.1）。"""
    if not points:
        return []
    out: List[Dict] = []
    anchor = _parse_date(points[0].date)
    bucket: Dict = {}
    for pp in points:
        d = _parse_date(pp.date)
        idx = (d - anchor).days // freq_days
        if bucket and idx != bucket["_idx"]:
            out.append({"date": bucket["open_date"], "open": bucket["open"],
                        "high": bucket["high"], "low": bucket["low"], "close": bucket["close"],
                        "n": bucket["n"]})
            bucket = {}
        if not bucket:
            bucket = {"_idx": idx, "open_date": pp.date, "open": pp.price,
                      "high": pp.price, "low": pp.price, "close": pp.price, "n": 1}
        else:
            bucket["high"] = max(bucket["high"], pp.price)
            bucket["low"] = min(bucket["low"], pp.price)
            bucket["close"] = pp.price
            bucket["n"] += 1
    if bucket:
        out.append({"date": bucket["open_date"], "open": bucket["open"],
                    "high": bucket["high"], "low": bucket["low"], "close": bucket["close"],
                    "n": bucket["n"]})
    return out

# -*- coding: utf-8 -*-
"""Iris 数据模型。字段与 docs/data-schema.md v1 保持一致；改字段必须同步文档。"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List


@dataclass
class SkuAttributes:
    vram_gb: float = 0.0
    tdp_w: float = 0.0
    cooling: str = ""        # 1fan / 2fan / 3fan / 水冷
    warranty_years: int = 0
    benchmark: float = 0.0   # 统一基准分（R03 性能分）


@dataclass
class Product:
    product_id: str
    name: str
    category: str
    launch_date: str
    lifecycle_family: str
    status: str = "active"


@dataclass
class Sku:
    sku_id: str
    product_id: str
    brand: str
    tier: str                # entry / mid / high（初值，M5 起按 R03 属性复核）
    channel: str
    attributes: SkuAttributes
    launch_price: int = 0


@dataclass
class PricePoint:
    date: str                # YYYY-MM-DD
    price: int               # 元，正整数
    quality: str = "confirmed"


@dataclass
class PriceSeries:
    sku_id: str
    source: str = "synthetic-demo"
    points: List[PricePoint] = field(default_factory=list)


@dataclass
class EventItem:
    event_id: str
    type: str                # launch / promo / policy / supply
    title: str
    date: str                # YYYY-MM-DD
    scope: str               # all | product_id
    confidence: str = "reported"  # official / reported / synthetic

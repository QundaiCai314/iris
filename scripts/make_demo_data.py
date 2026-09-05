# -*- coding: utf-8 -*-
"""演示数据生成器（M1.2）。显卡场景合成价格序列（RTX 5080/5070Ti/5070）。

剧本（对应产品叙事，2026-09 视角）：
- 5080：2025-01-30 上市。上市后正常降价；2025-06 双十一前促销谷；
  2025-09 起行情上行（AI/矿需求），2026-05 冲高后高位盘整（现价处 365 天约 85% 分位）。
- 5070Ti：类似但温和（+8% 量级）。
- 5070：整体平缓（几乎无供给冲击），作为「降档替代」对照。
- 所有 SKU 叠加年度大促谷（618 / 双11）。
数据为合成，逐条 source=synthetic-demo；后续用真实价格点替换/扩充（B01）。
"""
import json
import math
import os
import random
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data", "demo")
END_DATE = date(2026, 9, 3)          # 「今天」前的最新数据日
RNG = random.Random(20260904)        # 固定种子，可复现

PRODUCTS = [
    {"product_id": "rtx5080",  "name": "RTX 5080 16G",  "category": "显卡",
     "launch_date": "2025-01-30", "lifecycle_family": "gpu", "status": "active"},
    {"product_id": "rtx5070ti", "name": "RTX 5070 Ti 16G", "category": "显卡",
     "launch_date": "2025-02-20", "lifecycle_family": "gpu", "status": "active"},
    {"product_id": "rtx5070",  "name": "RTX 5070 12G",  "category": "显卡",
     "launch_date": "2025-03-05", "lifecycle_family": "gpu", "status": "active"},
]

# 每 SKU 的 launch_price 已含品牌/档次定位（R03：同渠道可比；属性给齐）
SKUS = [
    # product_id, sku_id, brand, tier, channel, attrs, launch_price
    ("rtx5080", "rtx5080-asus-tuf-mid",  "asus",      "mid",   "jd",   dict(vram_gb=16, tdp_w=320, cooling="3fan",  warranty_years=3, benchmark=100.0), 8599),
    ("rtx5080", "rtx5080-msi-ventus-entry", "msi",    "entry", "jd",   dict(vram_gb=16, tdp_w=320, cooling="2fan",  warranty_years=3, benchmark=96.0),  8299),
    ("rtx5080", "rtx5080-colorful-igame-high", "colorful", "high", "jd", dict(vram_gb=16, tdp_w=320, cooling="3fan", warranty_years=3, benchmark=103.0), 8999),
    ("rtx5070ti", "rtx5070ti-msi-mid", "msi", "mid", "jd", dict(vram_gb=16, tdp_w=300, cooling="3fan", warranty_years=3, benchmark=85.0), 6499),
    ("rtx5070ti", "rtx5070ti-gigabyte-entry", "gigabyte", "entry", "jd", dict(vram_gb=16, tdp_w=300, cooling="2fan", warranty_years=3, benchmark=84.0), 6299),
    ("rtx5070", "rtx5070-gigabyte-mid", "gigabyte", "mid", "jd", dict(vram_gb=12, tdp_w=250, cooling="3fan", warranty_years=3, benchmark=70.0), 4299),
    ("rtx5070", "rtx5070-msi-entry", "msi", "entry", "jd", dict(vram_gb=12, tdp_w=250, cooling="2fan", warranty_years=3, benchmark=68.0), 4199),
    # 低价渠道对照（pdd，渠道折扣 ~4%）
    ("rtx5080", "rtx5080-msi-ventus-entry-pdd", "msi", "entry", "pdd", dict(vram_gb=16, tdp_w=320, cooling="2fan", warranty_years=3, benchmark=96.0), 7950),
    ("rtx5070", "rtx5070-gigabyte-mid-pdd", "gigabyte", "mid", "pdd", dict(vram_gb=12, tdp_w=250, cooling="3fan", warranty_years=3, benchmark=70.0), 4120),
]

EVENTS = [
    dict(event_id="launch-5080", type="launch", title="RTX 5080 发布", date="2025-01-30", scope="rtx5080", confidence="official"),
    dict(event_id="launch-5070ti", type="launch", title="RTX 5070 Ti 发布", date="2025-02-20", scope="rtx5070ti", confidence="official"),
    dict(event_id="launch-5070", type="launch", title="RTX 5070 发布", date="2025-03-05", scope="rtx5070", confidence="official"),
    dict(event_id="promo-618-2025", type="promo", title="2025 618 大促", date="2025-06-18", scope="all", confidence="official"),
    dict(event_id="promo-1111-2025", type="promo", title="2025 双11 大促", date="2025-11-11", scope="all", confidence="official"),
    dict(event_id="promo-618-2026", type="promo", title="2026 618 大促", date="2026-06-18", scope="all", confidence="official"),
    dict(event_id="promo-1111-2026", type="promo", title="2026 双11 大促（预报）", date="2026-11-11", scope="all", confidence="synthetic"),
    dict(event_id="supply-2025-11", type="supply", title="行情启动：AI 需求与供给紧张报道", date="2025-11-01", scope="rtx5080,rtx5070ti", confidence="reported"),
    dict(event_id="supply-2026-05", type="supply", title="抢购潮与渠道溢价峰值", date="2026-05-15", scope="rtx5080", confidence="reported"),
    dict(event_id="policy-2026-03", type="policy", title="显卡进口/税率调整传闻", date="2026-03-01", scope="all", confidence="reported"),
]

# ---------- 价格成分 ----------

def launch_date_of(product_id: str) -> date:
    for p in PRODUCTS:
        if p["product_id"] == product_id:
            return date.fromisoformat(p["launch_date"])
    raise KeyError(product_id)


def decay_factor(months: float) -> float:
    """生命周期衰减（R02 §3 量级：半年 -18% 左右、一年约 -23%、之后趋缓）。
    分段月乘：<=6 月 -3%/月；6-18 月 -0.8%/月；>18 月 -0.3%/月。"""
    f = 1.0
    if months <= 6:
        return (1 - 0.030) ** months
    f = (1 - 0.030) ** 6
    if months <= 18:
        return f * (1 - 0.008) ** (months - 6)
    return f * (1 - 0.008) ** 12 * (1 - 0.003) ** (months - 18)


def _lerp(start: date, end: date, d: date) -> float:
    total = (end - start).days
    if total <= 0:
        return 1.0
    t = (d - start).days / total
    return max(0.0, min(1.0, t))


def shock_factor(product_id: str, d: date) -> float:
    """供给/需求冲击。5080：2025-09-01 起上行至 2026-05-15 峰值 +42%，
    之后高位小幅回落（2026-09-03 约 +35%）。5070Ti：+8% 温和；5070：几乎平缓。"""
    if product_id == "rtx5080":
        if d < date(2025, 9, 1):
            return 1.0
        if d <= date(2026, 5, 15):
            return 1.0 + 0.42 * _lerp(date(2025, 9, 1), date(2026, 5, 15), d)
        return 1.42 - 0.06 * _lerp(date(2026, 5, 15), date(2026, 12, 31), d)
    if product_id == "rtx5070ti":
        if d < date(2025, 11, 1):
            return 1.0
        return 1.0 + 0.08 * _lerp(date(2025, 11, 1), date(2026, 12, 31), d)
    if product_id == "rtx5070":
        if d < date(2025, 11, 1):
            return 1.0
        return 1.0 + 0.05 * _lerp(date(2025, 11, 1), date(2026, 12, 31), d)
    return 1.0


# (名称, 窗口起月日, 谷月日, 窗口末日, 最大折扣)
PROMOS = [
    ("618", (5, 20), (6, 18), (6, 22), 0.11),
    ("1111", (10, 15), (11, 11), (11, 15), 0.13),
]


def promo_factor(d: date) -> float:
    """大促折扣：从窗口起线性加深到谷日，之后快速恢复（谷日折扣最大）。"""
    for _name, (m0, d0), (mg, dg), (m1, d1), dip in PROMOS:
        start = date(d.year, m0, d0)
        trough = date(d.year, mg, dg)
        end = date(d.year, m1, d1)
        if start <= d <= trough:
            t = (d - start).days / max(1, (trough - start).days)
            return 1.0 - dip * (0.35 + 0.65 * t)   # 谷日约 -dip
        if trough < d <= end:
            t = (d - trough).days / max(1, (end - trough).days)
            return 1.0 - dip * max(0.0, 0.5 - 0.5 * t)
    return 1.0


def generate_series(sku: dict, product_id: str) -> list:
    """逐日生成：price = launch_price * decay * shock * promo * noise(AR1)。"""
    start = launch_date_of(product_id)
    price = sku["launch_price"]
    noise = 0.0
    pts = []
    d = start
    while d <= END_DATE:
        months = (d - start).days / 30.44
        base = sku["launch_price"] * decay_factor(months) * shock_factor(product_id, d)
        noise = 0.88 * noise + RNG.gauss(0, 0.0035)
        p = base * promo_factor(d) * (1 + noise)
        price = max(1, int(round(p)))
        pts.append({"date": d.isoformat(), "price": price, "quality": "confirmed"})
        d += timedelta(days=1)
    return pts


def main() -> None:
    os.makedirs(os.path.join(DATA_DIR, "prices"), exist_ok=True)
    sku_dicts = []
    for pid, sid, brand, tier, ch, attrs, lp in SKUS:
        sku_dicts.append({"sku_id": sid, "product_id": pid, "brand": brand, "tier": tier,
                          "channel": ch, "attributes": attrs, "launch_price": lp})
    with open(os.path.join(DATA_DIR, "catalog.json"), "w", encoding="utf-8") as f:
        json.dump({"products": PRODUCTS, "skus": sku_dicts}, f, ensure_ascii=False, indent=1)
    with open(os.path.join(DATA_DIR, "events.json"), "w", encoding="utf-8") as f:
        json.dump(EVENTS, f, ensure_ascii=False, indent=1)
    for pid, sid, _brand, _tier, _ch, _attrs, lp in SKUS:
        pts = generate_series({"launch_price": lp}, pid)
        with open(os.path.join(DATA_DIR, "prices", sid + ".json"), "w", encoding="utf-8") as f:
            json.dump({"sku_id": sid, "source": "synthetic-demo", "points": pts}, f, ensure_ascii=False)
    print("demo data written to", DATA_DIR)


if __name__ == "__main__":
    main()

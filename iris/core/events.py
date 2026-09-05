# -*- coding: utf-8 -*-
"""事件窗口统计（M3.1；口径出处：R01 §2-3）。

方法：
- 事件品相对对照组（同品类、未发生该事件的 product 日价中位）的对数价差路径；
  对照组不可用（如促销为品类级事件）时退化为事件品自身对数路径。
- 对照组差分只在对齐日历（两序列都有值）上累积；缺口 >7 天重置，防伪差分（与 stats 同口径）。
- 路径 = 自 E-before 起逐日累积，t 以事件日 E 为 0；输出 exp(累积)-1 百分比；
  跨事件 pooling 给均值 / 95% 带 / n（R01 §3 样本纪律：n<30 不给点概率的精神同样适用）。
"""
from __future__ import annotations
import math
from datetime import date, timedelta
from typing import Dict, List, Optional

from iris.core.models import EventItem, Product, Sku

WIN_BEFORE = 30
WIN_AFTER = 90
MAX_GAP_DAYS = 7


def product_daily_index(series_by_sku: Dict[str, object], skus: Dict[str, Sku],
                        product_id: str) -> Dict[str, float]:
    """product 级日价：当日该 product 全部 SKU 价格的中位数；无点则缺。"""
    sku_ids = [sid for sid, s in skus.items() if s.product_id == product_id]
    by_day: Dict[str, list] = {}
    for sid in sku_ids:
        for pp in series_by_sku[sid].points:
            by_day.setdefault(pp.date, []).append(pp.price)
    out: Dict[str, float] = {}
    for dt, vals in by_day.items():
        sv = sorted(vals)
        n = len(sv)
        out[dt] = float(sv[n // 2]) if n % 2 == 1 else (sv[n // 2 - 1] + sv[n // 2]) / 2.0
    return out


def category_control(series_by_sku: Dict[str, object], skus: Dict[str, Sku],
                     products: Dict[str, Product], exclude_product_id: str) -> Dict[str, float]:
    """对照组：同品类其他 product 逐日中位价，再取 product 间中位数（等权）。"""
    category = products[exclude_product_id].category
    others = [pid for pid, p in products.items()
              if p.category == category and pid != exclude_product_id]
    if not others:
        return {}
    by_day: Dict[str, list] = {}
    for pid in others:
        idx = product_daily_index(series_by_sku, skus, pid)
        for dt, v in idx.items():
            by_day.setdefault(dt, []).append(v)
    out: Dict[str, float] = {}
    for dt, vals in by_day.items():
        sv = sorted(vals)
        n = len(sv)
        out[dt] = float(sv[n // 2]) if n % 2 == 1 else (sv[n // 2 - 1] + sv[n // 2]) / 2.0
    return out


def _window_dates(keys, event_date: date, before: int, after: int):
    start = event_date - timedelta(days=before)
    for dt in keys:
        d = date.fromisoformat(dt)
        if d < start:
            continue
        if (d - event_date).days > after:
            break
        yield dt


def relative_path(series: Dict[str, float], control: Optional[Dict[str, float]],
                  event_date: date, before: int = WIN_BEFORE,
                  after: int = WIN_AFTER) -> Dict:
    """单起事件路径。control=None 时用自身对数路径（品类级事件，R01 §2 退化）。"""
    if control is None:
        keys = sorted(series)
        series_only = True
    else:
        keys = sorted(set(series) & set(control))
        series_only = False
    if not keys:
        return {"event_date": event_date.isoformat(), "path": {}, "n_days": 0}
    cum = 0.0
    path: Dict[int, float] = {}
    prev_d: Optional[date] = None
    prev_e = prev_c = None
    for dt in _window_dates(keys, event_date, before, after):
        d = date.fromisoformat(dt)
        e_now = series[dt]
        c_now = None if series_only else control[dt]
        t = (d - event_date).days
        if prev_d is None:
            path[t] = 0.0          # 基线（首个对齐日，约 E-before）
        elif (d - prev_d).days <= MAX_GAP_DAYS:
            de = math.log(e_now / prev_e)
            if series_only:
                cum += de
            else:
                cum += de - math.log(c_now / prev_c)
            path[t] = math.expm1(cum) * 100.0
        else:
            path[t] = 0.0          # 缺口重置：不跨缺口累积
        prev_d, prev_e = d, e_now
        if not series_only:
            prev_c = c_now
    return {"event_date": event_date.isoformat(), "path": path, "n_days": len(path)}


def summarize(paths: List[Dict], horizon_days: int) -> Dict:
    """pooling：各路径取 t<=horizon 最近点的累积百分比，输出均值/带/n。"""
    vals = []
    for p in paths:
        ts = [t for t in p["path"] if t <= horizon_days]
        if ts:
            vals.append(p["path"][max(ts)])
    if not vals:
        return {"horizon_days": horizon_days, "n": 0, "mean_pct": None,
                "ci95_pct": None, "min_pct": None, "max_pct": None}
    n = len(vals)
    mean = sum(vals) / n
    var = sum((v - mean) ** 2 for v in vals) / max(1, n - 1)
    se = math.sqrt(var / n) if n > 1 else 0.0
    return {"horizon_days": horizon_days, "n": n, "mean_pct": round(mean, 2),
            "ci95_pct": [round(mean - 1.96 * se, 2), round(mean + 1.96 * se, 2)],
            "min_pct": round(min(vals), 2), "max_pct": round(max(vals), 2)}


def event_scope_match(ev: EventItem, product_id: str) -> bool:
    if ev.scope == "all":
        return True
    return product_id in [s.strip() for s in ev.scope.split(",")]


def build_event_study(series_by_sku, skus, products, events: List[EventItem],
                      product_id: str, event_type: Optional[str] = None,
                      before: int = WIN_BEFORE, after: int = WIN_AFTER) -> Dict:
    """对某 product 的事件统计。单品级事件（launch/supply/policy）用对照组差分；
    品类级（promo）用自身路径。返回按事件类型分组的结果。"""
    index = product_daily_index(series_by_sku, skus, product_id)
    control = category_control(series_by_sku, skus, products, product_id)
    by_type: Dict[str, list] = {}
    for ev in events:
        if not event_scope_match(ev, product_id):
            continue
        if event_type and ev.type != event_type:
            continue
        use_control = None if ev.type == "promo" else control
        rp = relative_path(index, use_control, date.fromisoformat(ev.date),
                           before=before, after=after)
        rp["event_id"] = ev.event_id
        rp["event_type"] = ev.type
        by_type.setdefault(ev.type, []).append(rp)
    out: Dict[str, Dict] = {}
    for t, paths in by_type.items():
        horizons = {str(h): summarize(paths, h) for h in (30, 60, 90)}
        out[t] = {"events": [p["event_id"] for p in paths],
                  "horizons": horizons,
                  "paths": paths,
                  "control_used": (t != "promo" and bool(control)),
                  "control_note": ("" if control else "同品类无对照 product，退化为自身路径")}
    return out

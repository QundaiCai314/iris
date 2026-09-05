# -*- coding: utf-8 -*-
"""M5.3 替代品矩阵（R03 §2/§3 降级版：属性近邻配对，不跑 hedonic 回归）。

- 同型号行（same_product）：直接比价；价差只拆「可观察属性差」（档位/散热/保修/
  渠道/品牌标签），不可量化部分固定措辞「含品牌/售后/生态，值不值由你判断」
  （R03 §4 红线：不替用户做价值裁决）。
- 跨型号行（substitute）：按性能分对齐——每元性能 = benchmark / price（相对目标），
  同时给绝对价差；satisfies_need 由用途所需最低性能比 need_bench_ratio 决定
  （A4 假设：AI/3D 0.85、游戏 0.75、日常默认 0.6，可配置）。
- best_switch：alt_acceptable=no 只允许同型号行（换品牌/渠道，仍算「全新同款」）；
  alt_acceptable=yes 可含满足性能需求的跨型号降档；节省 >= A_SWITCH_MIN（8%，A5）
  才构成「显著更优」。
"""
from __future__ import annotations
from typing import Dict, List, Optional

A_SWITCH_MIN_PCT = 8.0                  # A5：与 iris/core/decision.py 同源（A5 门槛）
NEED_BENCH_RATIO = {"AI / 跑模型": 0.85, "3D / 视频创作": 0.85, "游戏": 0.75}
NEED_RATIO_DEFAULT = 0.6                # A4


def need_bench_ratio(purpose: Optional[str]) -> float:
    """用途 -> 所需最低性能比（相对目标型号基准分）。"""
    if not purpose:
        return NEED_RATIO_DEFAULT
    return NEED_BENCH_RATIO.get(purpose, NEED_RATIO_DEFAULT)


def _attr_diff(a, b) -> List[str]:
    """可观察属性差描述（A->B：以 b 为参照的差异）。"""
    out = []
    if a.cooling and b.cooling and a.cooling != b.cooling:
        out.append("散热 %s -> %s" % (a.cooling, b.cooling))
    if a.warranty_years != b.warranty_years:
        out.append("保修 %d -> %d 年" % (a.warranty_years, b.warranty_years))
    return out


def build_rows(target_sku_id: str, products: Dict, skus: Dict,
               price_map: Dict[str, int], purpose: Optional[str] = None) -> Dict:
    """生成替代矩阵：target 自身信息 + 全部可比 SKU 行（按节省降序标注）。"""
    t = skus[target_sku_id]
    t_prod = products[t.product_id]
    t_price = float(price_map.get(target_sku_id, 0) or 0)
    t_bench = t.attributes.benchmark or 1.0
    need_ratio = need_bench_ratio(purpose)
    rows: List[Dict] = []
    for sid, s in skus.items():
        if sid == target_sku_id:
            continue
        price = price_map.get(sid)
        if price is None or not price:
            continue
        same = s.product_id == t.product_id
        bench = s.attributes.benchmark or 0.0
        bench_ratio = round(bench / t_bench, 4)
        diff_abs = int(price) - int(t_price)
        diff_pct = round(diff_abs / t_price * 100.0, 2) if t_price else 0.0
        per_yuan = round(bench / price * 1000.0, 3) if price else 0.0
        per_yuan_t = round(t_bench / t_price * 1000.0, 3) if t_price else 0.0
        if same:
            satisfies = True

            attrs = ([("档位 %s -> %s" % (t.tier, s.tier))]
                     if t.tier != s.tier else []) + _attr_diff(t.attributes,
                                                               s.attributes)
            note_parts = attrs + (["渠道 %s -> %s" % (t.channel, s.channel)]
                                  if t.channel != s.channel else [])
            if s.brand != t.brand:
                note_parts.append("品牌 %s -> %s（溢价成分含售后/生态/叙事，"
                                  "值不值由你判断）" % (t.brand, s.brand))
            row_type = "same_product"
            row_note = "同型号换品牌/渠道：" + ("；".join(note_parts) if note_parts
                                                 else "属性一致仅比价")
        else:
            s_prod = products.get(s.product_id)
            if s_prod is None or s_prod.category != t_prod.category:
                continue                    # 只比较同品类（上下位替代）
            satisfies = bench >= t_bench or bench >= t_bench * need_ratio
            row_type = "substitute"
            row_note = ("跨型号%s替代：按性能分对齐——每元性能为目标 %s%%"
                        % ("降档" if bench < t_bench else "升档",
                           round(per_yuan / per_yuan_t * 100.0, 1)
                           if per_yuan_t else 0))
        rows.append({
            "row_type": row_type,
            "sku_id": sid,
            "product_id": s.product_id,
            "label": "%s %s %s" % (s.brand.upper(), s.product_id.upper(), s.tier),
            "brand": s.brand, "tier": s.tier, "channel": s.channel,
            "benchmark": bench, "bench_ratio": bench_ratio,
            "price": int(price), "saving_abs": -diff_abs, "saving_pct": -diff_pct,
            "diff_pct": diff_pct,
            "per_yuan": per_yuan, "per_yuan_target": per_yuan_t,
            "satisfies_need": satisfies,
            "need_bench_ratio": need_ratio,
            "note": row_note,
        })
    rows.sort(key=lambda r: (0 if r["row_type"] == "same_product" else 1,
                             r["satisfies_need"] is False,
                             -r["saving_abs"]))
    return {
        "target": {"sku_id": target_sku_id,
                   "label": "%s %s %s" % (t.brand.upper(), t.product_id.upper(), t.tier),
                   "price": int(t_price), "benchmark": t_bench,
                   "per_yuan": round(t_bench / t_price * 1000.0, 3) if t_price else 0.0},
        "rows": rows,
        "method_note": ("R03 §2/§3 降级版：属性近邻配对直接比价，不做 hedonic 回归"
                        "（同型号 SKU 样本少）；可量化项 = 总价差与属性清单，品牌/"
                        "售后/生态为不可观测项，价值判断交给用户"),
        "ref": "R03 §2-4",
    }


def best_switch(target_sku_id: str, products: Dict, skus: Dict,
                price_map: Dict[str, int], purpose: Optional[str] = None,
                alt_acceptable: str = "no") -> Optional[Dict]:
    """最佳换购候选：规则 = 允许范围（同型号 or 含降档）x satisfies_need x
    节省 >= A5；多候选取节省最大者（同额取每元性能高者）。"""
    mx = build_rows(target_sku_id, products, skus, price_map, purpose=purpose)
    best: Optional[Dict] = None
    for r in mx["rows"]:
        if not r["satisfies_need"]:
            continue
        if alt_acceptable != "yes" and r["row_type"] != "same_product":
            continue
        if r["saving_pct"] < A_SWITCH_MIN_PCT:
            continue
        if best is None or (r["saving_pct"], r["per_yuan"]) > (best["saving_pct"],
                                                               best["per_yuan"]):
            best = r
    if best is None:
        return None
    out = dict(best)
    out["row_type"] = best["row_type"]

    out["rule"] = ("A5 门槛：节省 >= %.0f%% 且满足用途最低性能比 %.2f"
                   % (A_SWITCH_MIN_PCT, need_bench_ratio(purpose)))
    return out

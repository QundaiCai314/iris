# -*- coding: utf-8 -*-
"""决策卡 JSON 结构（M2.5；schema 文档 docs/card-schema.md）。

v1 范围：meta + stats + p1（事件/替代/决策由 M3/M5 填充，字段预留）。
校验函数 validate_card：所有对外数字字段与 source_ref 结构检查。
"""
from __future__ import annotations
from typing import Dict, List

REQUIRED_META = ["product_id", "sku_id", "asof_date", "generated_at", "engine_version"]
REQUIRED_P1 = ["window_days", "drop", "n", "confidence", "method", "method_note", "direction"]


def build_card(product_id: str, sku_id: str, asof_date: str, stats: Dict,
               p1_windows: Dict, engine_version: str = "0.2.0") -> Dict:
    card = {
        "schema_version": "1.0",
        "meta": {"product_id": product_id, "sku_id": sku_id,
                 "asof_date": asof_date, "generated_at": asof_date,
                 "engine_version": engine_version},
        "stats": stats,
        "p1": p1_windows,
        "events": None,      # M3 填充
        "alternatives": None,  # M5 填充
        "decision": None,    # M5 填充
        "evidence": [],      # 依据链：{ref, note}，M3/M5 追加
    }
    return card


def validate_card(card: Dict) -> List[str]:
    errs: List[str] = []
    if card.get("schema_version") != "1.0":
        errs.append("schema_version 应为 1.0")
    meta = card.get("meta") or {}
    for k in REQUIRED_META:
        if k not in meta:
            errs.append("meta 缺字段: %s" % k)
    stats = card.get("stats")
    if not stats or "last_price" not in stats:
        errs.append("stats 缺 last_price")
    if "lookbacks" not in (stats or {}):
        errs.append("stats 缺 lookbacks")
    p1 = card.get("p1") or {}
    if "60" not in p1:
        errs.append("p1 缺 60 天主窗")
    for w, fc in p1.items():
        if not isinstance(fc, dict):
            errs.append("p1.%s 非对象" % w)
            continue
        for k in REQUIRED_P1:
            if k not in fc:
                errs.append("p1.%s 缺字段 %s" % (w, k))
        if fc.get("confidence") == "sufficient":
            for k in ("probability", "ci95", "hits"):
                if k not in fc:
                    errs.append("p1.%s 置信充足但缺 %s" % (w, k))
        else:
            if fc.get("confidence") != "insufficient":
                errs.append("p1.%s confidence 非法: %r" % (w, fc.get("confidence")))
    return errs

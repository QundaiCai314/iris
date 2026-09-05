# -*- coding: utf-8 -*-
"""异常状态门控（M3.3；出处：R02 §4 + 总纲 1.2）。

触发条件（任一即门控；命中后日历 / 生命周期代理权重下调并提示「非常规行情」）：
1) 波动率分位 >= vol_threshold（初值 0.90，可配置）；
2) 最近 supply 事件（60 天内，scope 匹配该 product）。
"""
from __future__ import annotations
from datetime import date, timedelta
from typing import Dict, List, Optional

from iris.core.events import event_scope_match
from iris.core.models import EventItem

VOL_THRESHOLD = 0.90
SUPPLY_LOOKBACK_DAYS = 60


def recent_supply(events: List[EventItem], product_id: str, asof: date,
                  lookback_days: int = SUPPLY_LOOKBACK_DAYS) -> Optional[EventItem]:
    for ev in events:
        if ev.type != "supply":
            continue
        if not event_scope_match(ev, product_id):
            continue
        d = date.fromisoformat(ev.date)
        if d <= asof and (asof - d).days <= lookback_days:
            return ev
    return None


def check_gate(vol_pct_position: Optional[float], events: List[EventItem],
               product_id: str, asof: date, vol_threshold: float = VOL_THRESHOLD) -> Dict:
    reasons: List[str] = []
    if vol_pct_position is not None and vol_pct_position >= vol_threshold:
        reasons.append("波动率分位 %.2f 超过阈值 %.2f" % (vol_pct_position, vol_threshold))
    sup = recent_supply(events, product_id, asof)
    if sup is not None:
        reasons.append("60 天内有供需事件: %s (%s)" % (sup.title, sup.date))
    return {"abnormal": bool(reasons), "reasons": reasons,
            "note": "非常规行情：日历与生命周期代理权重下调，优先实时分位与事件窗口（R02 §4）"
                    if reasons else "",
            "vol_threshold": vol_threshold}

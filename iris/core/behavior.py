# -*- coding: utf-8 -*-
"""M10 行为提示层（behavior hints）：检测用户侧非理性噪音并给中性提示。

定位与红线：
- 不改数学模型：G/U/R/buffer/P2 一律不动；提示只影响「怎么读卡」，不影响裁决。
- 规则确定性：同样输入 -> 同样提示集合，可复现、可测试。
- 文案红线：复用 decision.BANNED_WORDS 与 _check_copy，不制造焦虑（禁止
  倒计时/限量/催促式话术），只做降温与提醒。
- 不替用户裁决：提示措辞为「可以注意 / 建议隔天再看」级别，不下命令。

规则（v1，4 条；输入全部来自已有卡片字段，不新增后端依赖）：
1. promo_halo   —— 30 天内有大促 + 裁决为 buy：大促氛围放大「现在不买就亏了」
   的感觉，提示裁决口径里没有情绪项（evidence 引 R01）。
2. high_percentile_rally —— 现价处于 90 天高分位（>=0.7）+ 近 4 周收盘反弹
   （最后一根周收盘 > 3 根前）：别把几天反弹当成趋势反转，看的是主窗口。
3. rerun_anxiety —— 同一会话重算次数 >= 3：重跑本身可能是焦虑信号；参数没变
   反复重算不会改变结论，提示先离开再看。
4. fresh_card —— 刚答完问卷拿到首张卡：立刻下单容易冲动，建议隔天回来复核。
"""
from __future__ import annotations
from typing import Dict, List, Optional

from iris.core.decision import _check_copy

HIGH_POS_THRESHOLD = 0.70      # 90 天分位 >= 70% 视为「高位」
RALLY_WEEKS = 4                # 周线反弹窗口（最后收盘 vs 3 根前）
RERUN_ANXIETY_MIN = 3          # 重算 >= 3 次触发焦虑提示


def _promo_within(upcoming: Optional[List[Dict]], days: int) -> Optional[Dict]:
    for ev in (upcoming or []):
        if ev.get("type") == "promo" and (ev.get("days_ahead") or 0) <= days:
            return ev
    return None


def _week_rally(kline: Optional[List[Dict]]) -> bool:
    if not kline or len(kline) < RALLY_WEEKS:
        return False
    last = kline[-1].get("close")
    base = kline[-RALLY_WEEKS].get("close")
    return bool(last and base and last > base)


def build_behavior_hints(card: Dict, rerun_count: int = 0,
                         just_resolved: bool = False,
                         profile: Optional[Dict] = None) -> List[Dict]:
    """从已构建的决策卡提取行为提示（确定性、无副作用、文案过红线扫描）。

    rerun_count: /api/recompute 在本会话内的累计次数（0 = 首次出卡）。
    just_resolved: True = 用户刚走完问卷拿到首张卡（用于 fresh_card）。
    profile: 可选用户画像（若传入或 card["profile"] 存在，可激活行为去偏误助推）。
    """
    hints: List[Dict] = []
    dec = card.get("decision") or {}
    rec = dec.get("recommendation")
    stats = card.get("stats") or {}
    pos90 = ((stats.get("lookbacks") or {}).get("90") or {}).get("pct_position")
    upcoming = ((card.get("events") or {}).get("upcoming")) or []
    promo = _promo_within(upcoming, 30)

    if promo and rec == "buy":
        hints.append({
            "rule": "promo_halo",
            "text": ("大促氛围会放大「现在不买就亏了」的感觉——但你的卡是按历史"
                     "同价位段窗口算的，裁决里没有情绪这一项。历史大促窗口的平均"
                     "折扣见「条件与事件」页，别让倒计时替你做决定。"),
            "ref": "R01 事件窗口 + D3 不制造焦虑"})

    if pos90 is not None and pos90 >= HIGH_POS_THRESHOLD and _week_rally(card.get("kline")):
        hints.append({
            "rule": "high_percentile_rally",
            "text": ("最近几周价格在反弹、且现价已处于近 90 天 %.0f%% 分位——反弹"
             "容易让人怕「越等越贵」。这张卡看的是 %d 天窗口的平均规律，"
             "不是明天的涨跌；分位越高说明当前位置历史上越偏贵。"
             % (pos90 * 100, (dec.get("window_days") or 60))),
            "ref": "stats.lookbacks.90 + 周线"})

    if rerun_count >= RERUN_ANXIETY_MIN:
        hints.append({
            "rule": "rerun_anxiety",
            "text": ("你已经重算了 %d 次——反复调整假设通常说明心里已经偏向前一个"
                     "答案。参数没变时结论不会变；建议先离开页面，隔天用同一份"
                     "画像再看一次这张卡。" % rerun_count),
            "ref": "D3 不制造焦虑（降温提示）"})

    if just_resolved and rerun_count == 0:
        hints.append({
            "rule": "fresh_card",
            "text": ("刚答完问卷就下单容易冲动：问卷答案已经存档，建议隔天回来"
                     "再看一次这张卡——结论没变再买也不迟。"),
            "ref": "D3 不制造焦虑（降温提示）"})

    # Skill: lifecycle-obsolescence-guard（耐用品换代背刺高危预警）
    lc = card.get("lifecycle") or {}
    if lc:
        bri = lc.get("bri", 0.0)
        days_to_next = lc.get("days_to_next_gen", 999)
        hurdle_met = lc.get("hurdle_met", False)
        hurdle_pct = lc.get("hurdle_threshold_pct", 30.0)
        drawdown = lc.get("current_drawdown_pct", 0.0)
        if (bri >= 0.65 or days_to_next <= 60) and not hurdle_met:
            hints.append({
                "rule": "backstab_risk_alert",
                "text": ("【换代背刺预警】该型号上市已达代际末期（距下一代发布预计不足 %d 天），"
                         "现价降幅（%.1f%%）尚未达到该品类清仓补偿门槛（需降 %.0f%%）；"
                         "降价不足以补偿失去下代新特性的效用损失，若非急用建议等待下一代。"
                         % (days_to_next, drawdown, hurdle_pct)),
                "ref": "耐用品生命周期与背刺风险指数 (BRI)"
            })

    # Skill: behavioral-debiasing-nudges（单次使用成本助推，防范冲动闲置）
    prof = profile or card.get("profile") or {}
    intensity = prof.get("usage_intensity")
    if intensity in ("rarely", "low"):
        price_val = float(stats.get("last_price") or (dec.get("decomposition") or {}).get("price") or 0.0)
        if price_val > 0:
            weekly_h = 2.0 if intensity == "rarely" else 5.0
            total_deprec = price_val * 0.40
            total_hours = 2.0 * 52.0 * weekly_h
            cph = total_deprec / total_hours if total_hours > 0 else 0.0
            hints.append({
                "rule": "cost_per_use_nudge",
                "text": ("【单次使用成本助推】按当前使用频次折算，2 年内单小时真实使用折旧成本"
                         "约达 %.1f 元/小时；对于低频使用场景，高单价硬件存在闲置折旧风险，"
                         "建议客观评估实际开机频次，防范冲动消费。" % cph),
                "ref": "行为经济学去偏误（单次使用成本助推）"
            })

    _check_copy([h["text"] for h in hints])
    return hints

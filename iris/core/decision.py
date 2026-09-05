# -*- coding: utf-8 -*-
"""M5 决策引擎：期望值分解 / 买·等·换 裁决 / P2 概率 / 红绿灯与条件句。

口径与出处（方法 v1，代码引用总纲 §2.5、R05 §3）：
- 框架：等待 = 实物期权（最优停止）。裁决比较四块：
  G = 等待期望收益（数据）：P1 同分位段历史窗口 wait_stats.saving_pct
      （等满窗、以窗内最低价成交，低于现价记节省；口径见 iris/core/p1.py）；
  U = 等待期效用损失 = 价格 x 月损失率 x 等待天数/30.44；月损失率 = 使用强度基准
      x 享乐系数 x 等待档位系数（A1/A2：方向出处 R05 §2.3/§3，数值待 B05 标定）；
  R = 等待风险 = 历史损失率（窗口内最低价高于现价）+ 供需升温附加（A3，条件生效）；
  buffer = 风险厌恶缓冲 = A6 基数 x (0.5 + 波动率分位)：波动率分位越高触发带越宽
      （(S,s) 规则，总纲 §1.2：不确定性升高 -> 继续观望更合理）。
- 裁决：净期望 net = G - U - R - buffer；net > 0 -> 等，否则 -> 买。
- 必需 / 立即需要：闸门直通「买」（M4 分流：只做渠道比价，不跑时机模型）。
- P2 =「现在买是 60 天视野内最优决策的概率」：对（等待档位系数 / 最晚期限 /
  波动率分位 / 通胀预期缩放 / 供需附加）做确定性分层小网格扰动，统计「裁决 = 买」
  的份额。替代品维度不进 P2（另列 alternatives 节），避免双重记账。
- 红线：样本不足（n < 30）降级为低置信（只黄不红）；文案禁用承诺词（_BANNED）；
  替代品「值不值由你判断」不替用户裁决。
"""
from __future__ import annotations
import itertools
from typing import Dict, List, Optional

HORIZON_DAYS = 60                       # 定版主窗（用户 2026-09-04 确认，30/180 辅助）

# ---- 假设参数（A 编号；方向有出处，数值待 B05 问卷实验标定，展示可调） ----
A_BUF_BASE_PCT = 2.0                    # A6：缓冲基数（现价 %）；buffer = base x (0.5+vol)
A_SUPPLY_PCT = 1.0                      # A3：供需升温附加（现价 %），P2 扰动 0~2%
A_WARM_PCT = 3.0                        # A6b：净等待收益 >= 3% -> 红灯（别现在买）
A_SWITCH_MIN_PCT = 8.0                  # A5：替代品「显著更优」节省门槛（%）
NEED_RATIO_DEFAULT = 0.6                # A4：日常用途的最低性能比（见 alternatives.NEED_BENCH_RATIO）
ASSUMPTION_REF = "假设 A1-A7（方向有出处：R05 §2.3/§3、总纲 §1.3；数值待 B05 标定，展示时可调）"

# A1/A2：U 的构成系数
INTENSITY_MONTHLY_PCT = {"rarely": 0.5, "low": 1.0, "medium": 2.0, "high": 3.5}
HEDONIC_MULT = {"hedonic": 1.6, "utilitarian": 1.0}
WAIT_TIER_MULT = {"low": 1.6, "mid": 1.2, "high": 0.8}
TIER_ORDER = ["low", "mid", "high"]

# A7：通胀预期对「等待节省」的缩放扰动（中心恒为 1.0：点估计仍锚定历史，
# 用户预期只加宽 P2 不确定性带；方向：水平上升->早买、不确定->更宽，总纲 §1.3）
PRICE_VIEW_FACTORS = {
    "up": [0.7, 1.0],
    "stable": [0.9, 1.0, 1.1],
    "down": [1.0, 1.2],
    "uncertain": [0.7, 1.0, 1.3],
}

# 红线措辞：任何生成文案不得出现（测试覆盖）
BANNED_WORDS = ["保证", "稳赚", "必涨", "必跌", "包票", "绝对", "100%会", "稳赚不赔"]


def wait_window_days(profile: Dict, horizon: int = HORIZON_DAYS) -> int:
    """最晚期限 -> 可等待天数上限（now=0；within_30=30；其余按主窗 60 封顶）。"""
    deadline = profile.get("deadline", "none")
    if deadline == "now":
        return 0
    if deadline == "within_30":
        return min(30, horizon)
    return horizon                      # within_90 / none：引擎只按 60 天主窗记账


def pick_p1_window(fc_windows: Dict, wait_days: int) -> Dict:
    """按等待天数选同窗 P1 结果（30/60/180 取就近的较长窗）。"""
    key = "30" if wait_days <= 45 else ("60" if wait_days <= 120 else "180")
    if str(key) not in fc_windows:
        raise KeyError("缺少 %s 天 P1 窗口（可用: %s）" % (key, ",".join(sorted(fc_windows))))
    return fc_windows[str(key)]


def usage_loss_monthly_pct(profile: Dict) -> float:
    """U 月损失率（现价 %/月）= 强度 x 享乐 x 等待档位（A1/A2）。"""
    intensity = profile.get("usage_intensity", "low")
    hedonic = profile.get("hedonic", "utilitarian")
    tier = profile.get("wait_tier", "mid")
    return (INTENSITY_MONTHLY_PCT.get(intensity, 1.0)
            * HEDONIC_MULT.get(hedonic, 1.0)
            * WAIT_TIER_MULT.get(tier, 1.2))


def _money(pct: float, price: float) -> float:
    return round(pct * price / 100.0, 2)


def supply_hot(profile: Dict) -> bool:
    """供需升温标记：用户感知缺货/涨价消息多（问卷 supply_news）即视为生效。"""
    return profile.get("supply_news") == "yes"


def decompose(profile: Dict, p1fc: Dict, vol_pct: Optional[float],
              supply_on: bool = False) -> Dict:
    """期望值分解。p1fc 须与 wait_window_days(profile) 同窗（30/60）。全字段可解释。"""
    wait_days = wait_window_days(profile)
    price = float(p1fc.get("last_price", 0) or 0)
    ws = p1fc.get("wait_stats") or {}
    n_win = ws.get("n_windows", 0) if ws else 0
    saving_pct = float(ws.get("saving_pct", 0.0) or 0.0) if ws else 0.0
    loss_pct = float(ws.get("loss_pct", 0.0) or 0.0) if ws else 0.0
    v = min(1.0, max(0.0, vol_pct if vol_pct is not None else 0.5))
    u_pct = usage_loss_monthly_pct(profile) * wait_days / 30.44
    buffer_pct = A_BUF_BASE_PCT * (0.5 + v)
    supply_pct = A_SUPPLY_PCT if supply_on else 0.0
    r_pct = loss_pct + supply_pct
    net_pct = saving_pct - u_pct - r_pct - buffer_pct
    return {
        "wait_days": wait_days,
        "n_windows": n_win,
        "price": int(round(price)),
        "saving_pct": round(saving_pct, 4),
        "saving_yuan": _money(saving_pct, price),       # G 等待期望收益
        "u_pct": round(u_pct, 4),
        "u_yuan": _money(u_pct, price),                 # U 等待效用损失
        "loss_history_pct": round(loss_pct, 4),         # R 的历史部分
        "supply_premium_pct": round(supply_pct, 4),     # R 的供需附加
        "r_pct": round(r_pct, 4),
        "r_yuan": _money(r_pct, price),                 # R 等待风险合计
        "buffer_pct": round(buffer_pct, 4),
        "buffer_yuan": _money(buffer_pct, price),       # 风险厌恶缓冲（随波动率加宽）
        "net_pct": round(net_pct, 4),
        "net_yuan": _money(net_pct, price),             # 净等待期望（>0 倾向等）
        "params": {
            "usage_loss_monthly_pct": round(usage_loss_monthly_pct(profile), 4),
            "vol_pct_position": round(v, 4),
            "supply_hot": supply_on,
            "assumption": ASSUMPTION_REF,
        },
    }


def _confidence(p1fc: Dict) -> str:
    n = int(p1fc.get("n", 0) or 0)
    min_n = int(p1fc.get("min_n", 30) or 30)
    return "sufficient" if n >= min_n else "low"


def _alt_allowed(best_alt: Optional[Dict], profile: Dict) -> bool:
    if not best_alt:
        return False
    if profile.get("alt_acceptable") == "yes":
        return True
    return best_alt.get("row_type") == "same_product"   # 只接受全新同款：同型号换品牌/渠道


def decide(profile: Dict, fc_windows: Dict, vol_pct: Optional[float],
           best_alt: Optional[Dict] = None, supply_on: Optional[bool] = None) -> Dict:
    """主裁决。返回完整决策对象（decomposition + 红绿灯 + 换购建议）。"""
    if supply_on is None:
        supply_on = supply_hot(profile)
    dec: Dict = {"supply_hot": supply_on, "assumption": ASSUMPTION_REF}
    wait_days = wait_window_days(profile)
    necessary = profile.get("necessity") == "essential"

    # 闸门：必需 / 立即需要 -> 买（渠道比价优先；同型号更便宜渠道可触发换购）
    if necessary or wait_days == 0:
        if _alt_allowed(best_alt, profile) and best_alt["saving_pct"] >= A_SWITCH_MIN_PCT:
            rec, light = "switch", "yellow"
            dec["mode"] = "gate_switch"
        else:
            rec, light = "buy", "green"
            dec["mode"] = "essential" if necessary else "deadline_now"
        dec.update({
            "recommendation": rec, "traffic_light": light,
            "window_days": 0, "n_windows": None,
            "decomposition": None,
            "note": ("必需品类：时点不重要，只做渠道比价（R05 §1）"
                     if necessary else "最晚期限 = 现在：等不起，时点不构成问题"),
            "confidence": "sufficient",
            "switch_to": best_alt if rec == "switch" else None,
        })
        return dec

    p1fc = pick_p1_window(fc_windows, wait_days)
    conf = _confidence(p1fc)
    comp = decompose(profile, p1fc, vol_pct, supply_on)
    net = comp["net_pct"]
    rec = "wait" if net > 0 else "buy"

    # 替代品显著更优 -> 换（默认只允许同型号；可接受平替时允许跨型号降档）
    if _alt_allowed(best_alt, profile) and best_alt.get("satisfies_need") \
            and best_alt["saving_pct"] >= A_SWITCH_MIN_PCT:
        rec = "switch"

    if rec == "buy":
        light = "green"
    elif rec == "switch":
        light = "yellow"
    else:  # wait：净期望越大越倾向「别现在买」；样本不足只给黄灯
        light = "yellow" if (conf == "low" or net < A_WARM_PCT) else "red"

    dec.update({
        "recommendation": rec, "traffic_light": light,
        "mode": "timing_engine", "window_days": wait_days,
        "n_windows": comp["n_windows"], "decomposition": comp,
        "confidence": conf,
        "note": ("" if conf == "sufficient"
                 else "同分位段历史窗口 < 30：净期望仅为低置信参考，不构成红灯依据"),
        "switch_to": best_alt if rec == "switch" else None,
    })
    return dec


def p2_probability(profile: Dict, fc_windows: Dict, vol_pct: Optional[float],
                   supply_on: Optional[bool] = None) -> Dict:
    """P2：参数扰动网格中「裁决 = 买」的份额（确定性、可复现）。

    维度（v1）：等待档位系数（A2）、等待天数（期限，30/60 两窗各自取数）、
    波动率分位（buffer 宽窄）、通胀预期缩放（A7）、供需附加（A3，升温时开启）。
    """
    if supply_on is None:
        supply_on = supply_hot(profile)
    necessary = profile.get("necessity") == "essential"
    if necessary or wait_window_days(profile) == 0:
        return {"probability": 1.0, "n_scenarios": 1, "buy_count": 1,
                "wait_count": 0, "confidence": "sufficient",
                "method": "gate-not-timing",
                "note": "必需/立即需要：闸门直通买，时点模型不适用（P2 定义退化为 1.0）",
                "dimensions": {}}

    v = min(1.0, max(0.0, vol_pct if vol_pct is not None else 0.5))
    tier = profile.get("wait_tier", "mid")
    idx = TIER_ORDER.index(tier) if tier in TIER_ORDER else 1
    tier_mults = sorted({WAIT_TIER_MULT[t] for t in
                         TIER_ORDER[max(0, idx - 1): idx + 2]}, reverse=True)
    vol_levels = sorted({round(x, 2) for x in
                         (max(0.0, v - 0.15), v, min(1.0, v + 0.15))})
    w0 = wait_window_days(profile)
    day_levels = sorted({max(0, w0 - 15), w0, min(HORIZON_DAYS, w0 + 15)})
    day_levels = [d for d in day_levels if d > 0]
    view_factors = PRICE_VIEW_FACTORS.get(profile.get("price_view", "stable"), [1.0])
    supply_levels = [0.0, A_SUPPLY_PCT] if supply_on else [0.0]

    dims = {"wait_tier_mult": tier_mults, "wait_days": day_levels,
            "vol_pct": vol_levels, "price_view_factor": view_factors,
            "supply_premium_pct": supply_levels}
    scenarios = list(itertools.product(tier_mults, day_levels, vol_levels,
                                       view_factors, supply_levels))
    buy_count = 0
    seen = set()
    n_scen = 0
    for tier_mult, days, vv, view_f, sup_pct in scenarios:
        key = (tier_mult, days, vv, view_f, sup_pct)
        if key in seen:
            continue
        seen.add(key)
        n_scen += 1
        p1fc = pick_p1_window(fc_windows, days)
        ws = p1fc.get("wait_stats") or {}
        saving = (ws.get("saving_pct", 0.0) or 0.0) if ws else 0.0
        loss = (ws.get("loss_pct", 0.0) or 0.0) if ws else 0.0

        u = (INTENSITY_MONTHLY_PCT.get(profile.get("usage_intensity", "low"), 1.0)
             * HEDONIC_MULT.get(profile.get("hedonic", "utilitarian"), 1.0)
             * tier_mult * days / 30.44)
        buffer = A_BUF_BASE_PCT * (0.5 + vv)
        net = view_f * saving - u - loss - sup_pct - buffer
        if net <= 0:
            buy_count += 1
    p2 = round(buy_count / n_scen, 4) if n_scen else 1.0
    conf = _confidence(pick_p1_window(fc_windows, w0))
    return {"probability": p2, "n_scenarios": n_scen, "buy_count": buy_count,
            "wait_count": n_scen - buy_count, "confidence": conf,
            "method": "perturbation-grid-v1",
            "note": ("确定性参数扰动网格（分层采样 v1）：P2 = 各（档位/期限/波动率/"
                     "通胀预期/供需）情景下「裁决 = 买」的份额；替代品维度单列于 "
                     "alternatives 节，不进 P2"),
            "dimensions": dims}


def traffic_light(rec: str, net_pct: float, confidence: str = "sufficient") -> str:
    """红绿灯映射（M5.4）：买->绿；换->黄；等且净期望 >= A_WARM -> 红，其余黄。"""
    if rec == "buy":
        return "green"
    if rec == "switch":
        return "yellow"
    if confidence == "low" or net_pct < A_WARM_PCT:
        return "yellow"
    return "red"


def _check_copy(texts: List[str]) -> None:
    for t in texts:
        for w in BANNED_WORDS:
            if w in t:
                raise ValueError("生成文案含红线词「%s」: %s" % (w, t))


def build_conditions(profile: Dict, dec: Dict, p2: Dict,
                     upcoming: Optional[List[Dict]] = None) -> List[Dict]:
    """条件句：「若……则……」由参数自动生成；期限/预算改动即变（M5.4 验收）。"""
    conds: List[Dict] = []
    rec = dec["recommendation"]
    comp = dec.get("decomposition") or {}
    note_ref = comp.get("params", {}).get("assumption", ASSUMPTION_REF)
    deadline_txt = {"none": "不急着用（默认看 60 天）", "within_30": "30 天内要用",
                    "within_90": "90 天内要用（引擎按 60 天主窗记账）",
                    "now": "现在就要"}.get(profile.get("deadline", "none"), "")

    if dec.get("mode", "").startswith("essential"):
        conds.append({"scenario": "essential",
                      "text": "若属必需品类：时点不重要 -> 先比同款不同渠道价差，谁便宜买谁；省下的才是真钱。",
                      "ref": "R05 §1"})
    elif dec.get("mode") == "deadline_now":
        conds.append({"scenario": "deadline_now",
                      "text": "若最晚期限是现在：等待省的钱换不回缺货/晚用的代价 -> 直接买。",
                      "ref": "R05 §3"})
    else:

        wd = comp.get("wait_days", 60)
        if rec == "buy":
            supply_tail = ("近期缺货/涨价消息多，等 = 赌再涨（已计入 R）。"
                           if dec.get("supply_hot") else "无额外风险项。")
            conds.append({
                "scenario": "buy_now",
                "text": ("若 %s：等待净期望 %.2f%%（<=0，等不划算）-> 现在买更优；%s"
                         % (deadline_txt, comp.get("net_pct") or 0.0, supply_tail)),
                "ref": note_ref})
        else:
            # 等或换的裁决，都给出「只认这一款、不换」视角下的等待账
            if rec == "wait" or comp.get("net_pct", 0) > 0:
                low_n = "，n<30 仅参考" if (comp.get("n_windows") or 0) < 30 else ""
                conds.append({
                    "scenario": "wait" if rec == "wait" else "wait_if_same_only",
                    "text": ("若 %s%s：历史同价位段窗口等 %d 天，平均可省约 %.2f%%"
                             "（%d 个窗口%s），扣等待成本与风险后净期望 %.2f%%"
                             " -> 可等。中途若要用，按最新价格重跑本卡。"
                             % (deadline_txt,
                                "，且只认准这一款、不接受平替" if rec == "switch" else "",
                                wd, comp.get("saving_pct"),
                                comp.get("n_windows"), low_n,
                                comp.get("net_pct"))),
                    "ref": "p1.wait_stats + %s" % note_ref})
            if rec == "wait" and dec["traffic_light"] == "red":
                conds.append({
                    "scenario": "wait_strong",
                    "text": ("红灯：净等待期望 ≥ %.1f%%（现价 %.0f 元）—— 这个位置"
                             "历史上更容易买到更便宜，别急着下单；价格回落到 "
                             "%.0f 元（跌 %s%%）以下可重跑本卡复核。"
                             % (A_WARM_PCT, comp.get("price", 0),
                                comp.get("price", 0) * 0.95, 5)),
                    "ref": "总纲 §2.5 / A6b"})
    if dec.get("supply_hot") and comp:
        conds.append({
            "scenario": "supply",
            "text": "若最近缺货/涨价消息多：供需紧张期间「等」要承受再涨风险"
                    "（已计入 R 的供需附加），急用就别拖。",
            "ref": "总纲 §1.3 / A3"})

    for ev in (upcoming or []):
        kind = ev.get("type")

        if kind == "promo":
            suffix = ""
            if ev.get("beyond_days", 0) > 0:
                suffix = ("；该窗口超出 60 天主窗 %d 天，作为备选触发点不作承诺"
                          % ev["beyond_days"])
            conds.append({
                "scenario": "event_" + str(ev.get("date", "")),
                "text": ("若能等到 %s（约 %d 天后）：%s%s"
                         % (ev.get("date", ""), ev.get("days_ahead", 0),
                            ev.get("summary_text", "大促窗口是历史折扣集中期，"
                                                   "幅度看事件统计"), suffix)),
                "ref": "R01 事件窗口（n 小仅量级参考）"})
        elif kind == "launch":
            conds.append({
                "scenario": "event_" + ev.get("date", ""),
                "text": ("若在等换代：%s（%s）后旧型号通常有调价窗口，"
                         "历史幅度见事件统计，别在发布前接盘最高价。"
                         % (ev.get("title", ""), ev.get("date", ""))),
                "ref": "R01 事件窗口"})

    switch = dec.get("switch_to")
    if switch:
        conds.append({
            "scenario": "switch",
            "text": ("若%s：%s 现价 %d 元，比目标省 ¥%d（%s%%），性能为目标的 "
                     "%s%%；若只是预算或价格问题，先看替代矩阵——值不值由你判断。"
                     % (("能接受同款换品牌/渠道" if switch.get("row_type") == "same_product"
                         else "能接受降档替代"),
                        switch.get("label", switch.get("sku_id", "")),
                        switch.get("price", 0), int(switch.get("saving_abs", 0)),
                        switch.get("saving_pct", 0), switch.get("bench_ratio", 1.0) * 100)),
            "ref": "R03 §3（A5 门槛 %s%%）" % A_SWITCH_MIN_PCT})
    if p2.get("confidence") == "low":
        conds.append({"scenario": "low_sample",
                      "text": "样本提示：该价位段匹配的历史窗口不足 30 个，以上数字是"
                              "低置信参考，请结合区间看，不构成承诺。",
                      "ref": "总纲 §2.6 样本纪律"})
    _check_copy([c["text"] for c in conds])
    return conds
def plain_language(profile: Dict, dec: Dict, p2: Dict,
                   fc_windows: Dict) -> Dict:
    """M7.2 通俗结论：把裁决翻成一句零术语的大白话（Web 首屏 Banner 同源）。

    只在 P1/P2 有数值时才引用概率；必需/期限闸门直接给行动指令；
    红线词由 build_decision 里 _check_copy 统一拦截（测试覆盖）。
    """
    rec = dec["recommendation"]
    mode = dec.get("mode", "")
    comp = dec.get("decomposition") or {}
    wd = int(comp.get("wait_days") or dec.get("window_days") or HORIZON_DAYS)
    p1w = fc_windows.get(str(wd)) or fc_windows.get("60") or {}
    p1_prob = p1w.get("probability")
    p2_prob = (p2 or {}).get("probability")
    if p1_prob is not None:
        p1_prob = int(round(float(p1_prob) * 100.0))
    if p2_prob is not None:
        p2_prob = int(round(float(p2_prob) * 100.0))

    if mode.startswith("essential"):
        s = dec.get("switch_to") or {}
        if s:
            return {"verdict": "买便宜的那个",
                    "text": ("必需品类时点不重要，但别买贵：%s 现价 %d 元，比你现在"
                             "看的省 ¥%d（约 %s%%）——同型号挑便宜的买，性能一样。"
                             % (s.get("label") or s.get("sku_id")
                                or "更便宜的候选", int(s.get("price") or 0),
                                int(s.get("saving_abs") or 0),
                                "%.1f" % (s.get("saving_pct") or 0)))}
        return {"verdict": "直接买",
                "text": "这东西属于必需品：什么时候买差别不大，重点是别买贵——"
                        "同款先比价，哪个渠道便宜就买哪个，省下的才是真钱。"}
    if mode == "deadline_now":
        return {"verdict": "直接买",
                "text": "你现在就要用、等不起：为等降价而耽误正事，省下的钱抵不过"
                        "麻烦，直接买最省心。"}
    if rec == "switch":
        s = dec.get("switch_to") or {}
        return {"verdict": "换成它",
                "text": ("换个买法更划算：%s 现价 %d 元，比你现在看的省 ¥%d"
                         "（约 %s%%），性能约为你原目标的 %s%%，满足你的用途"
                         "——值不值由你判断。"
                         % (s.get("label") or s.get("sku_id") or "更便宜的候选",
                            int(s.get("price") or 0),
                            int(s.get("saving_abs") or 0),
                            "%.1f" % (s.get("saving_pct") or 0),
                            "%.0f" % ((s.get("bench_ratio") or 1.0) * 100)))}
    if rec == "wait":
        why = ""
        if p1_prob is not None:
            why += ("历史数据显示，价格走到现在这个位置后，未来 %d 天内降价 ≥5%%"
                    " 的概率约为 %d%%；" % (wd, p1_prob))
        elif comp:
            why += ("历史上和你情况相似时，等满 %d 天平均能等到便宜 %.1f%%"
                    "（%d 个历史窗口）；" % (wd, comp.get("saving_pct") or 0,
                                            comp.get("n_windows") or 0))
        if p2_prob is not None:
            why += ("把等待期里你用不到的损失也算进去，'现在买'仍然是最优的"
                    "概率只有 %d%%。" % p2_prob)
        else:
            why += "历史样本还不多，结论先当参考，别急着下单。"
        if profile.get("deadline", "none") in ("none", "within_90"):
            tail = "你并不急着用：先按兵不动，过一阵子再来问一次，让数字替你做决定。"
        else:
            tail = "你只能再等约 %d 天：先按兵不动，临近期限时再来问一次。" % wd
        return {"verdict": "先等一等", "text": why + tail}
    # rec == buy（时机引擎）
    head = ""
    if p2_prob is not None:
        head = ("综合你的使用情况模拟后，'现在买'仍然是最优的概率约 %d%%——"
                % p2_prob)
    if dec.get("supply_hot"):
        tail = "最近缺货、涨价的消息多，再等可能等来更贵的价格：在你接受的价位内，现在买更省心。"
    else:
        tail = "等待省下的钱抵不过等待期里你用不到的损失，现在买更划算。"
    return {"verdict": "现在买", "text": head + tail}



def build_decision(profile: Dict, fc_windows: Dict, vol_pct: Optional[float],
                   best_alt: Optional[Dict] = None,
                   upcoming: Optional[List[Dict]] = None) -> Dict:
    """M5 汇总入口：decide + P2 + 条件句 + plain_language 通俗层 -> decision 字段。"""
    supply_on = supply_hot(profile)
    dec = decide(profile, fc_windows, vol_pct, best_alt=best_alt, supply_on=supply_on)
    p2 = p2_probability(profile, fc_windows, vol_pct, supply_on=supply_on)
    conds = build_conditions(profile, dec, p2, upcoming)
    pl = plain_language(profile, dec, p2, fc_windows)
    _check_copy([pl["verdict"], pl["text"]])
    return {"recommendation": dec["recommendation"],
            "traffic_light": dec["traffic_light"],
            "mode": dec.get("mode"), "window_days": dec.get("window_days"),
            "n_windows": dec.get("n_windows"), "confidence": dec.get("confidence"),
            "note": dec.get("note", ""), "plain_language": pl,
            "decomposition": dec.get("decomposition"),
            "p2": p2, "conditions": conds, "switch_to": dec.get("switch_to"),
            "params_note": ASSUMPTION_REF}

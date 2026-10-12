# -*- coding: utf-8 -*-
"""金融计量经济学与行为金融模型（M16 前沿深化；纯标准库）。

理论文献出处与定位：
1. 均值回归与奥恩斯坦-乌伦贝克过程（Ornstein-Uhlenbeck / Vasicek 1977 等价 AR(1) 离散表达）：
   价格围绕局部均衡中枢的偏离与均值回归衰减速度（半衰期 Half-Life）测算。
   方程：dP_t = kappa * (mu - P_t) dt + sigma dW_t
   离散自回归 OLS：Delta P_t = alpha + beta * P_{t-1} + epsilon_t
   回归速率 kappa = -ln(1 + beta)，半衰期 t_{1/2} = ln(2) / kappa。
   注：作为局部价格偏离衰减尺度的解释工具；耐用品存在换代下行趋势，数据不支持均值回归时不给出半衰期。
2. 累积前景理论与损失厌恶（Cumulative Prospect Theory, Tversky & Kahneman 1992）：
   量化展示同一价格波动在不同损失厌恶偏好假设下的主观等价金额（Certainty Equivalent）。
   价值函数：v(x) = x^alpha (x >= 0), v(x) = -lambda * (-x)^beta (x < 0)，经典默认值 lambda = 2.25。
   概率加权函数（Tversky & Kahneman 1992）：
   w^+(p) = p^gamma / (p^gamma + (1-p)^gamma)^(1/gamma) (收益加权, gamma=0.61)
   w^-(p) = p^delta / (p^delta + (1-p)^delta)^(1/delta) (损失加权, delta=0.69)
   注：CPT 用于帮助用户理解自身主观风险厌恶对决策感受的影响，不直接替代客观期望收益与决策规则。
"""
from __future__ import annotations
import math
from datetime import date
from typing import Dict, List, Optional

from iris.core.models import PricePoint


def _d(p: PricePoint) -> date:
    return date.fromisoformat(p.date)


def fit_ornstein_uhlenbeck(points: List[PricePoint], lookback_days: int = 180) -> Dict:
    """奥恩斯坦-乌伦贝克 (Ornstein-Uhlenbeck) 价格均值回归模型。
    
    使用纯标准库普通最小二乘法 (OLS) 拟合离散时间 AR(1) 差分方程：
    Delta P_t = alpha + beta * P_{t-1} + e_t
    若 beta < 0，存在均值回归效应：
    - 长期均衡中枢 mu = -alpha / beta
    - 回归速度 kappa = -ln(1 + beta)
    - 半衰期 half_life = ln(2) / kappa (天)
    """
    if len(points) < 15:
        return {
            "is_mean_reverting": False,
            "half_life_days": None,
            "equilibrium_price": None,
            "current_deviation_yuan": 0,
            "current_deviation_pct": 0.0,
            "regime": "insufficient_data",
            "citation": "Vasicek (1977) / Ornstein-Uhlenbeck Process",
            "note": "样本点不足 15 天，无法可靠拟合 AR(1) 均值回归参数",
        }

    asof = _d(points[-1])
    # 截取近 lookback_days 日历天的数据
    pts = [p for p in points if (asof - _d(p)).days <= lookback_days]
    if len(pts) < 15:
        pts = points[-min(len(points), 60):]

    xs: List[float] = []  # P_{t-1}
    ys: List[float] = []  # Delta P_t = P_t - P_{t-1}
    for i in range(1, len(pts)):
        p0 = float(pts[i - 1].price)
        p1 = float(pts[i].price)
        xs.append(p0)
        ys.append(p1 - p0)

    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n

    # OLS 估计斜率 beta 与截距 alpha
    cov_xy = sum((xs[i] - mean_x) * (ys[i] - mean_y) for i in range(n))
    var_x = sum((xs[i] - mean_x) ** 2 for i in range(n))

    if var_x < 1e-9:
        beta = 0.0
        alpha = mean_y
    else:
        beta = cov_xy / var_x
        alpha = mean_y - beta * mean_x

    last_p = float(points[-1].price)

    # 判断均值回归显著性 (beta < 0 且 1 + beta > 0)
    if beta < -1e-6 and (1.0 + beta) > 0.0:
        is_mr = True
        kappa = -math.log(1.0 + beta)
        half_life = round(math.log(2.0) / kappa, 1)
        mu = round(-alpha / beta, 1)
        dev_yuan = round(last_p - mu, 1)
        dev_pct = round((dev_yuan / mu) * 100.0, 2)
        if dev_pct > 2.0:
            regime = "overvalued"
            regime_desc = f"高位溢价区（高于均衡中枢 ¥{mu:.0f} 约 {dev_pct:+.1f}%，预计约 {half_life:.0f} 天衰减一半溢价）"
        elif dev_pct < -2.0:
            regime = "undervalued"
            regime_desc = f"低位折价区（低于均衡中枢 ¥{mu:.0f} 约 {abs(dev_pct):.1f}%，低位窗口通常较为短暂）"
        else:
            regime = "fair"
            regime_desc = f"处于合理中枢区（现价接近均衡线 ¥{mu:.0f}）"
    else:
        is_mr = False
        kappa = 0.0
        half_life = None
        mu = round(mean_x, 1)
        dev_yuan = round(last_p - mu, 1)
        dev_pct = round((dev_yuan / mu) * 100.0, 2)
        regime = "trending_or_random_walk"
        regime_desc = "近期价格呈现单边趋势或随机游走，弱均值回归特征"

    return {
        "is_mean_reverting": is_mr,
        "half_life_days": half_life,
        "equilibrium_price": int(round(mu)),
        "current_deviation_yuan": int(round(dev_yuan)),
        "current_deviation_pct": dev_pct,
        "speed_kappa": round(kappa, 4),
        "regime": regime,
        "regime_desc": regime_desc,
        "citation": "Ornstein-Uhlenbeck / Vasicek (1977) Econometric Mean-Reversion",
    }


def cumulative_prospect_theory_valuation(
    saving_yuan: float,
    loss_yuan: float,
    p_save: float,
    p_loss: float,
    alpha: float = 0.88,
    beta: float = 0.88,
    lambda_param: float = 2.25,
    gamma_gain: float = 0.61,
    delta_loss: float = 0.69,
) -> Dict:
    """累积前景理论（Cumulative Prospect Theory）主观心理价值测算。
    
    参数：
    - saving_yuan: 预期降价节省金额 (元, >= 0)
    - loss_yuan: 预期涨价损失金额 (元, >= 0)
    - p_save: 降价节省发生概率 [0, 1]
    - p_loss: 涨价损失发生概率 [0, 1]
    - lambda_param: 损失厌恶系数（经典实证值 2.25，损失带来的心理痛苦是收益的 2.25 倍）
    - gamma_gain, delta_loss: 概率权重曲率参数 (Tversky & Kahneman 1992)
    """
    p_s = max(0.0, min(1.0, float(p_save)))
    p_l = max(0.0, min(1.0, float(p_loss)))

    # 概率加权函数 w(p)
    def w_gain(p: float) -> float:
        if p <= 1e-9:
            return 0.0
        if p >= 1.0 - 1e-9:
            return 1.0
        denom = (p ** gamma_gain + (1.0 - p) ** gamma_gain) ** (1.0 / gamma_gain)
        return (p ** gamma_gain) / denom if denom > 0 else p

    def w_loss(p: float) -> float:
        if p <= 1e-9:
            return 0.0
        if p >= 1.0 - 1e-9:
            return 1.0
        denom = (p ** delta_loss + (1.0 - p) ** delta_loss) ** (1.0 / delta_loss)
        return (p ** delta_loss) / denom if denom > 0 else p

    wg = w_gain(p_s)
    wl = w_loss(p_l)

    # 价值函数 v(x)
    v_gain = (max(0.0, saving_yuan) ** alpha)
    v_loss = -lambda_param * (max(0.0, loss_yuan) ** beta)

    # 前景理论主观总效用 V
    prospect_v = wg * v_gain + wl * v_loss

    # 确定性等价 (Certainty Equivalent, CE)：将主观效用反解回等价金额
    if prospect_v >= 0:
        ce_yuan = int(round(prospect_v ** (1.0 / alpha)))
    else:
        ce_yuan = -int(round((-prospect_v / lambda_param) ** (1.0 / beta)))

    # 客观数学期望金额
    expected_ev = int(round(p_s * saving_yuan - p_l * loss_yuan))

    # 损失厌恶心理折价 (Psychological Wedge)
    wedge_yuan = expected_ev - ce_yuan

    if ce_yuan > 0:
        behavior_advice = (
            f"在考虑 2.25 倍损失厌恶后，等待的心理确定性等价值为 +¥{ce_yuan}（客观期望值 +¥{expected_ev}）。"
            "潜在降价收益足以克服涨价焦虑，理性心理支持继续等待。"
        )
    elif expected_ev > 0 and ce_yuan <= 0:
        behavior_advice = (
            f"客观数学期望为正（+¥{expected_ev}），但在损失厌恶视角下主观心理等价值转负（¥{ce_yuan}）。"
            "说明您感受到的涨价断货痛苦放大了 2.25 倍；若您极度厌恶不确定性，现在买入符合风险规避偏好。"
        )
    else:
        behavior_advice = (
            f"客观期望与心理效用均为负（心理等价值 ¥{ce_yuan}）。"
            "等待既不划算又承受心理焦虑，强烈建议现在直接购买。"
        )

    return {
        "objective_expected_yuan": expected_ev,
        "prospect_value": round(prospect_v, 2),
        "certainty_equivalent_yuan": ce_yuan,
        "loss_aversion_wedge_yuan": wedge_yuan,
        "loss_aversion_ratio": lambda_param,
        "weighted_prob_gain": round(wg, 4),
        "weighted_prob_loss": round(wl, 4),
        "behavior_advice": behavior_advice,
        "citation": "Kahneman & Tversky (1979) / Cumulative Prospect Theory (1992)",
    }

# -*- coding: utf-8 -*-
"""电商 30 天价保看跌期权定价与渠道套利核算脚本。
将价保建模为平价看跌回望期权，计算公允退差期望并与跨渠道价差进行博弈裁决。
"""
import sys
import argparse

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def evaluate_price_protection(price_guaranteed: float, price_discount: float,
                               drop_prob: float, drop_pct: float) -> dict:
    spread = price_guaranteed - price_discount
    
    # 期望退差理论公允价值 (Put Option Value)
    expected_refund_yuan = round(price_guaranteed * (drop_pct / 100.0) * drop_prob, 2)
    
    # 净博弈差额: 理论退差期望 - 多付出的渠道溢价
    net_arbitrage_yuan = round(expected_refund_yuan - spread, 2)
    
    if net_arbitrage_yuan > 50.0:
        recommendation = "【优选带价保渠道 (如京东自营)】"
        reason = (
            f"30天内理论预期退差 ¥{expected_refund_yuan} 高于多付出的渠道价差 ¥{spread} (净期望 +¥{net_arbitrage_yuan})。"
            "相当于免费获赠一份高胜率看跌期权，兼得即刻使用与后续退差保障！"
        )
    elif net_arbitrage_yuan < -50.0:
        recommendation = "【优选低价直降渠道 (如拼多多百亿补贴)】"
        reason = (
            f"渠道价差达 ¥{spread}，而30天内退差期望仅为 ¥{expected_refund_yuan} (净期望 ¥{net_arbitrage_yuan})。"
            "价保服务溢价过高，直接省下真金白银更划算！"
        )
    else:
        recommendation = "【两渠道势均力敌·依偏好选择】"
        reason = (
            f"退差期望 ¥{expected_refund_yuan} 与渠道价差 ¥{spread} 相当 (价差相差仅 ¥{abs(net_arbitrage_yuan)})。"
            "若厌恶售后纠纷选带价保渠道，若追求绝对低价选直降渠道。"
        )
        
    return {
        "price_guaranteed": price_guaranteed,
        "price_discount": price_discount,
        "channel_spread_yuan": spread,
        "drop_probability_pct": round(drop_prob * 100, 1),
        "expected_drop_depth_pct": drop_pct,
        "put_option_fair_value_yuan": expected_refund_yuan,
        "net_arbitrage_yuan": net_arbitrage_yuan,
        "recommendation": recommendation,
        "reason": reason
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Price Protection Put Option Valuation")
    parser.add_argument("--price", type=float, required=True, help="Price with 30-day price guarantee (e.g. JD)")
    parser.add_argument("--alt_price", type=float, required=True, help="Price from discount channel without guarantee (e.g. PDD)")
    parser.add_argument("--drop_prob", type=float, default=0.45, help="30-day drop probability (0.0 to 1.0)")
    parser.add_argument("--drop_pct", type=float, default=6.0, help="Expected drop depth percentage if drop occurs")
    args = parser.parse_args()
    
    res = evaluate_price_protection(args.price, args.alt_price, args.drop_prob, args.drop_pct)
    print("="*60)
    print("电商 30 天价保期权定价与跨渠道博弈分析：")
    print(f"  - 带价保渠道价: {res['price_guaranteed']} 元  vs  直降渠道价: {res['price_discount']} 元 (渠道价差: {res['channel_spread_yuan']} 元)")
    print(f"  - 30 天内历史同分位跌破概率: {res['drop_probability_pct']}% (期望跌幅: {res['expected_drop_depth_pct']}%)")
    print(f"  - 30 天价保看跌期权公允价值 (Fair Put Premium): {res['put_option_fair_value_yuan']} 元")
    print(f"  - 期权净套利期望: {res['net_arbitrage_yuan']} 元")
    print(f"  - 核心决策建议: {res['recommendation']}")
    print(f"  - 详细逻辑: {res['reason']}")
    print("="*60)

# -*- coding: utf-8 -*-
"""行为经济学去偏误与单次使用成本助推核算脚本。
计算商家划线价虚高水分、单小时/单次使用真实成本，并生成行为助推自检清单。
"""
import sys
import argparse

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def evaluate_nudges(current_price: float, claimed_anchor: float,
                    residual_value: float, weekly_hours: float,
                    holding_years: float = 2.0) -> dict:
    # 1. 划线价去水分
    claimed_discount_pct = max(0.0, (claimed_anchor - current_price) / claimed_anchor * 100.0) if claimed_anchor > 0 else 0.0
    
    # 2. 真实使用成本透视 (Cost Per Hour)
    total_depreciation = max(0.0, current_price - residual_value)
    total_weeks = holding_years * 52.0
    total_hours = total_weeks * max(0.5, weekly_hours)
    
    cost_per_hour = total_depreciation / total_hours if total_hours > 0 else total_depreciation
    
    # 助推评级
    if cost_per_hour > 30.0:
        nudge_warning = "【高单价闲置预警】单小时使用成本超过 ¥30 元，属于重度吃灰高危区间！建议重新评估使用频次或选择入门型号。"
    elif cost_per_hour > 10.0:
        nudge_warning = "【中度成本提示】单小时成本约 ¥10~30 元，需保证稳定使用频率方可跑赢折旧。"
    else:
        nudge_warning = "【高性价比区间】高频充分利用，单小时使用折旧不足 ¥10 元，沉没效用充分释放！"
        
    return {
        "current_price": current_price,
        "claimed_anchor": claimed_anchor,
        "claimed_discount_pct": round(claimed_discount_pct, 1),
        "total_depreciation_yuan": round(total_depreciation, 2),
        "expected_total_hours": round(total_hours, 1),
        "cost_per_hour_yuan": round(cost_per_hour, 2),
        "nudge_warning": nudge_warning
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Behavioral Debiasing & Nudge Evaluator")
    parser.add_argument("--price", type=float, required=True, help="Current purchase price")
    parser.add_argument("--claimed_anchor", type=float, default=0.0, help="Merchant claimed anchor strikethrough price")
    parser.add_argument("--residual", type=float, default=0.0, help="Estimated resale residual value in 2 years")
    parser.add_argument("--weekly_hours", type=float, default=5.0, help="Estimated weekly usage hours")
    parser.add_argument("--years", type=float, default=2.0, help="Holding years")
    args = parser.parse_args()
    
    res = evaluate_nudges(args.price, args.claimed_anchor, args.residual, args.weekly_hours, args.years)
    print("="*60)
    print("行为经济学去偏误与使用成本透视结果：")
    if args.claimed_anchor > args.price:
        print(f"  - 商家宣传划线价: {args.claimed_anchor} 元 (宣称狂降 {res['claimed_discount_pct']}%)")
        print("  - 理性重锚提示: 划线价通常为数月前首发建议价，非近期常态中位数，切勿被锚定效应操纵！")
    print(f"  - 真实净折旧成本: {res['total_depreciation_yuan']} 元 (预估持有 {args.years} 年后残值 {args.residual} 元)")
    print(f"  - 预期累计使用: {res['expected_total_hours']} 小时 (基于每周 {args.weekly_hours} 小时)")
    print(f"  - 单小时真实使用成本: {res['cost_per_hour_yuan']} 元/小时")
    print(f"  - 助推建议: {res['nudge_warning']}")
    print("="*60)

# -*- coding: utf-8 -*-
"""以旧换新与国补最优化核算脚本。
计算能效补贴、补贴利用率，并对比一键以旧换新 vs 二手自售的净现金流。
"""
import sys
import argparse

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def calculate_subsidy(price: float, efficiency_tier: int = 1) -> dict:
    pct = 0.20 if efficiency_tier == 1 else 0.15
    cap = 2000.0 if efficiency_tier == 1 else 1500.0
    
    theoretical_subsidy = price * pct
    actual_subsidy = min(theoretical_subsidy, cap)
    effective_rate = (actual_subsidy / price) * 100.0 if price > 0 else 0.0
    
    return {
        "price": price,
        "efficiency_tier": efficiency_tier,
        "subsidy_rate_nominal": pct * 100.0,
        "actual_subsidy_yuan": round(actual_subsidy, 2),
        "effective_subsidy_rate": round(effective_rate, 2),
        "is_capped": theoretical_subsidy > cap,
        "surplus_over_cap": max(0.0, theoretical_subsidy - cap)
    }

def compare_paths(price: float, efficiency_tier: int,
                  old_market_val: float, old_platform_val: float,
                  tradein_bonus: float) -> dict:
    sub = calculate_subsidy(price, efficiency_tier)
    subsidy_yuan = sub["actual_subsidy_yuan"]
    
    # 路径 A: 电商一键以旧换新
    outflow_a = price - subsidy_yuan - old_platform_val - tradein_bonus
    
    # 路径 B: 二手自售 + 新机直购国补
    friction_cost = 50.0  # 假设二手平台包装/顺丰到付/沟通隐性摩擦
    outflow_b = price - subsidy_yuan - old_market_val + friction_cost
    
    diff = outflow_a - outflow_b
    
    recommendation = "路径B (二手自售)" if diff > 150 else "路径A (电商一键以旧换新)"
    
    return {
        "subsidy_info": sub,
        "path_a_outflow_yuan": round(outflow_a, 2),
        "path_b_outflow_yuan": round(outflow_b, 2),
        "diff_yuan": round(abs(diff), 2),
        "cheaper_path": "B (自售更省)" if diff > 0 else "A (以旧换新更省)",
        "recommendation": recommendation,
        "advice_text": (
            f"新机国补立减 ¥{subsidy_yuan}（实际优惠 {sub['effective_subsidy_rate']}%）。"
            f"方案A净支出 ¥{round(outflow_a, 2)}，方案B净支出 ¥{round(outflow_b, 2)}。"
            f"建议选择：{recommendation}。"
        )
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trade-in & National Subsidy Arbitrage Calculator")
    parser.add_argument("--price", type=float, required=True, help="New product price")
    parser.add_argument("--efficiency", type=int, default=1, choices=[1, 2], help="Energy efficiency tier (1 or 2)")
    parser.add_argument("--old_market", type=float, default=0.0, help="Old device second-hand market value")
    parser.add_argument("--old_platform", type=float, default=0.0, help="Old device platform trade-in appraisal")
    parser.add_argument("--tradein_bonus", type=float, default=0.0, help="Platform trade-in extra voucher bonus")
    args = parser.parse_args()
    
    res = compare_paths(args.price, args.efficiency, args.old_market, args.old_platform, args.tradein_bonus)
    print("="*60)
    print("国补与以旧换新决策测算结果：")
    print(f"  - 新机价格: {args.price} 元 (能效 {args.efficiency} 级)")
    print(f"  - 享受国补: {res['subsidy_info']['actual_subsidy_yuan']} 元 (有效补贴率: {res['subsidy_info']['effective_subsidy_rate']}%)")
    print(f"  - 方案A (电商一键以旧换新) 实际掏钱: {res['path_a_outflow_yuan']} 元")
    print(f"  - 方案B (二手自售+国补直购) 实际掏钱: {res['path_b_outflow_yuan']} 元")
    print(f"  - 建议结论: {res['recommendation']}")
    print(f"  - 解读说明: {res['advice_text']}")
    print("="*60)

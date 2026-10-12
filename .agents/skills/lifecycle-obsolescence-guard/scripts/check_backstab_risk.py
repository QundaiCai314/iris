# -*- coding: utf-8 -*-
"""耐用品生命周期与背刺风险指数计算脚本。
根据品类典型代际周期、已上市天数与现价跌幅，输出背刺指数 (BRI) 与清仓门槛判断。
"""
import sys
import argparse
from datetime import date, datetime

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

CATEGORY_CYCLES_DAYS = {
    "phone": 365,      # 手机一般 12 个月一换代
    "gpu": 730,        # 显卡一般 24 个月跨代大换代
    "console": 2555,   # 主机一般 7 年大代际，3-4 年半代 Pro 刷新
    "laptop": 365,     # 笔电随 CPU/GPU 每年刷新
    "default": 730
}

CLEARANCE_HURDLES_PCT = {
    "phone": 28.0,     # 手机临换代老款至少需降 28%
    "gpu": 35.0,       # 显卡临换代老款至少需降 35%
    "console": 20.0,
    "laptop": 25.0,
    "default": 30.0
}

def analyze_backstab_risk(category: str, launch_date_str: str,
                          current_price: float, launch_price: float,
                          asof_str: str = None) -> dict:
    asof = date.fromisoformat(asof_str) if asof_str else date.today()
    launch_d = date.fromisoformat(launch_date_str)
    
    cat_key = category.lower()
    cycle_days = CATEGORY_CYCLES_DAYS.get(cat_key, CATEGORY_CYCLES_DAYS["default"])
    hurdle_pct = CLEARANCE_HURDLES_PCT.get(cat_key, CLEARANCE_HURDLES_PCT["default"])
    
    elapsed_days = (asof - launch_d).days
    progress = max(0.0, elapsed_days / cycle_days)
    days_to_next = max(0, int(cycle_days - (elapsed_days % cycle_days)))
    
    drawdown_pct = max(0.0, (launch_price - current_price) / launch_price * 100.0) if launch_price > 0 else 0.0
    
    # 相位判定
    if progress < 0.25:
        phase = "Phase 1: 首发导入期 (新机溢价/产能爬坡)"
    elif progress < 0.65:
        phase = "Phase 2: 成熟放量期 (黄金购买期，性价比最高)"
    elif progress < 0.90:
        phase = "Phase 3: 换代预警期 (下一代临近，警惕背刺)"
    else:
        phase = "Phase 4: 清仓退市期 (折扣博弈，需核算清仓门槛)"
        
    # 背刺风险指数 BRI
    time_urgency = max(0.0, 1.0 - (days_to_next / 180.0))
    bri = time_urgency / (1.0 + drawdown_pct / 100.0)
    bri = round(min(1.0, max(0.0, bri)), 3)
    
    if bri >= 0.65:
        risk_level = "极高危·红色预警 (强烈建议等待下一代)"
    elif bri >= 0.35:
        risk_level = "中危·黄色谨慎 (仅限刚需，关注清仓门槛)"
    else:
        risk_level = "低危·绿色安全 (残值已消化或离换代尚远)"
        
    hurdle_met = drawdown_pct >= hurdle_pct
    hurdle_advice = (
        f"当前降幅 {drawdown_pct:.1f}% 已超过该品类清仓补偿门槛 ({hurdle_pct:.1f}%)，老款折价足以对冲新品代差，可以抄底！"
        if hurdle_met else
        f"当前降幅 {drawdown_pct:.1f}% 未达清仓补偿门槛 ({hurdle_pct:.1f}%)，降价不足以补偿失去下代新特性的效用损失，建议等下一代！"
    )
    
    return {
        "category": category,
        "elapsed_days": elapsed_days,
        "days_to_next_gen": days_to_next,
        "current_drawdown_pct": round(drawdown_pct, 2),
        "phase": phase,
        "bri": bri,
        "risk_level": risk_level,
        "hurdle_threshold_pct": hurdle_pct,
        "hurdle_met": hurdle_met,
        "hurdle_advice": hurdle_advice
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backstab Risk Index (BRI) Calculator")
    parser.add_argument("--category", type=str, default="gpu", choices=["phone", "gpu", "console", "laptop"], help="Product category")
    parser.add_argument("--launch_date", type=str, required=True, help="Launch date (YYYY-MM-DD)")
    parser.add_argument("--current_price", type=float, required=True, help="Current tracking price")
    parser.add_argument("--launch_price", type=float, required=True, help="Launch MSRP price")
    parser.add_argument("--asof", type=str, default=None, help="Reference asof date (default: today)")
    args = parser.parse_args()
    
    res = analyze_backstab_risk(args.category, args.launch_date, args.current_price, args.launch_price, args.asof)
    print("="*60)
    print(f"耐用品生命周期与背刺风险评估结果 [{args.category.upper()}]:")
    print(f"  - 已上市天数: {res['elapsed_days']} 天 (距下代预期发布: ~{res['days_to_next_gen']} 天)")
    print(f"  - 当前价格较首发跌幅: {res['current_drawdown_pct']}%")
    print(f"  - 所处生命周期相位: {res['phase']}")
    print(f"  - 背刺风险指数 (BRI): {res['bri']} -> {res['risk_level']}")
    print(f"  - 清仓补偿门槛分析: {res['hurdle_advice']}")
    print("="*60)

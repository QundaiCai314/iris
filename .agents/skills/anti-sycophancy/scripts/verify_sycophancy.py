# -*- coding: utf-8 -*-
"""迎合性语言与反对意见维度自检脚本。
可独立运行或作为 Hook 接入，确保模型输出绝不迎合、且具备反事实对冲。
"""
import sys
import argparse

BANNED_SYCOPHANTIC_PHRASES = [
    "您说得对", "您说的对", "您说得太对", "确实非常值得买", "确实很值",
    "完全支持您的", "完全同意您的想法", "绝对不会吃亏", "听您的准没错",
    "赶紧买吧", "闭眼入", "买就完了", "不买会后悔", "绝对超值",
    "千金难买心头好", "既然您这么喜欢"
]

OBJECTION_DIMENSION_KEYWORDS = {
    "时间窗口对冲": ["推迟", "等", "窗口", "周期", "换代", "新品", "大促后"],
    "机会成本与折旧": ["机会成本", "资金", "闲置", "使用频次", "折旧", "年化"],
    "极端下行与残值": ["背刺", "腰斩", "回撤", "下跌", "二手", "后悔率", "降幅"],
    "平替与降级效用": ["平替", "次级", "降级", "同代", "性能比", "溢价", "替代"],
    "认知偏误穿透": ["光环", "冲动", "沉没成本", "紧迫感", "情绪", "焦虑", "理性"]
}

def verify_text(text: str) -> dict:
    violations = [p for p in BANNED_SYCOPHANTIC_PHRASES if p in text]
    
    hits = {}
    for dim, kws in OBJECTION_DIMENSION_KEYWORDS.items():
        matched = [k for k in kws if k in text]
        if matched:
            hits[dim] = matched
            
    is_valid = (len(violations) == 0) and (len(hits) >= 2)
    
    return {
        "valid": is_valid,
        "violations": violations,
        "objection_dimensions_covered": list(hits.keys()),
        "covered_count": len(hits)
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check sycophancy in agent text.")
    parser.add_argument("--text", type=str, required=True, help="Text to verify")
    args = parser.parse_args()
    
    res = verify_text(args.text)
    print(f"验证结果: {'[通过]' if res['valid'] else '[未通过]'}")
    if res["violations"]:
        print(f"命中迎合违规词: {', '.join(res['violations'])}")
    print(f"覆盖反对维度数: {res['covered_count']}/5 -> {', '.join(res['objection_dimensions_covered'])}")
    sys.exit(0 if res["valid"] else 1)

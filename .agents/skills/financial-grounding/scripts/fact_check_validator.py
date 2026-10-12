# -*- coding: utf-8 -*-
"""金融抗幻觉与事实核查验证脚本。
检查：
1. 严禁词扫描（必涨/必跌/稳赚/绝对等）
2. 三级置信度标签扫描（Tier-1 / Tier-2 / Tier-3）
3. 关键政策术语规范性核验
"""
import sys
import argparse

BANNED_FINANCIAL_WORDS = [
    "必涨", "必跌", "稳赚", "保本", "绝对", "100%会", "包票", "零风险", "稳赚不赔"
]

CONFIDENCE_TIERS = [
    "事实", "数据归档", "可核验",
    "量化估计", "CI 95%", "置信区间", "低置信参考",
    "参数假定", "用户可调", "宏观政策研判"
]

MACRO_POLICY_TERMS = [
    "中央经济工作会议", "政治局会议", "以旧换新", "超长期特别国债",
    "扩大内需", "促消费", "国补", "能效补贴"
]

def validate_text(text: str) -> dict:
    violations = [w for w in BANNED_FINANCIAL_WORDS if w in text]
    
    tier_found = [t for t in CONFIDENCE_TIERS if t in text]
    
    policy_found = [p for p in MACRO_POLICY_TERMS if p in text]
    
    is_valid = len(violations) == 0
    
    return {
        "valid": is_valid,
        "violations": violations,
        "confidence_tags_detected": tier_found,
        "has_confidence_annotation": len(tier_found) > 0,
        "macro_policy_terms_used": policy_found
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check financial hallucination and grounding.")
    parser.add_argument("--text", type=str, required=True, help="Text to check")
    args = parser.parse_args()
    
    res = validate_text(args.text)
    print(f"金融安全核查: {'[通过]' if res['valid'] else '[拦截违规]'}")
    if res["violations"]:
        print(f"命中绝对化红线禁词: {', '.join(res['violations'])}")
    print(f"检出置信度标签: {', '.join(res['confidence_tags_detected']) if res['confidence_tags_detected'] else '无 (建议补充三级置信度标签)'}")
    print(f"检出宏观政策要素: {', '.join(res['macro_policy_terms_used']) if res['macro_policy_terms_used'] else '无'}")
    sys.exit(0 if res["valid"] else 1)

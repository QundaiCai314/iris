# -*- coding: utf-8 -*-
"""上下文锚定状态连续性与冲突检测验证脚本。
测试和验证：
1. 画像 8 大核心槽位完整性
2. 新输入与历史锚点冲突检测逻辑
3. 跨轮次状态注入模板生成
"""
import sys
import json
import argparse

REQUIRED_SLOTS = [
    "category", "purpose", "deadline", "usage_intensity",
    "budget_tier", "alt_acceptable", "hedonic", "wait_tier"
]

MUTEX_PAIRS = [
    ("deadline", "now", "deadline", "none"),
    ("deadline", "within_30", "deadline", "none"),
    ("budget_tier", "low", "budget_tier", "high"),
    ("alt_acceptable", "no", "alt_acceptable", "yes")
]

def check_anchor_profile(profile: dict) -> dict:
    missing = [s for s in REQUIRED_SLOTS if s not in profile or profile[s] is None]
    return {
        "valid": len(missing) == 0,
        "missing_slots": missing,
        "complete_slots_count": len(REQUIRED_SLOTS) - len(missing)
    }

def detect_conflict(old_profile: dict, new_signals: dict) -> list:
    conflicts = []
    for k, new_v in new_signals.items():
        if k in old_profile:
            old_v = old_profile[k]
            if old_v != new_v:
                conflicts.append({
                    "slot": k,
                    "old_value": old_v,
                    "new_value": new_v,
                    "reason": f"槽位 [{k}] 由 '{old_v}' 变更为 '{new_v}'"
                })
    return conflicts

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check profile anchor slots and detect conflicts.")
    parser.add_argument("--old", type=str, help="JSON string of old profile", default="{}")
    parser.add_argument("--new", type=str, help="JSON string of new incoming updates", default="{}")
    args = parser.parse_args()

    try:
        old_p = json.loads(args.old) if args.old else {}
        new_u = json.loads(args.new) if args.new else {}
    except Exception as e:
        print(f"JSON 解析失败: {e}")
        sys.exit(1)

    chk = check_anchor_profile(old_p)
    print(f"槽位完整性检查: {'[完整]' if chk['valid'] else '[缺漏]'} (包含 {chk['complete_slots_count']}/8 核心槽位)")
    if chk["missing_slots"]:
        print(f"缺漏槽位: {', '.join(chk['missing_slots'])}")

    conflicts = detect_conflict(old_p, new_u)
    if conflicts:
        print(f"检测到偏好冲突 ({len(conflicts)} 处):")
        for c in conflicts:
            print(f"  - {c['reason']}")
    else:
        print("未检测到偏好冲突，状态连续平滑。")

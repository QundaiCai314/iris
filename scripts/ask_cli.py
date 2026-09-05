# -*- coding: utf-8 -*-
"""M4 验收 CLI：问卷流程剧本。

用法：
  python scripts/ask_cli.py --case gpu      # 显卡（可选品，完整 8 题 + 贴现 3 小题）
  python scripts/ask_cli.py --case drug     # 药品（必需闸门，3 题）
  python scripts/ask_cli.py --interactive   # 人工交互模式
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from iris.agent.needs import (build_questions, parse_product_text, run_questionnaire,
                              validate_profile)

# 剧本应答（确定性）：值对应 question options 的 value
SCRIPTS = {
    "gpu": {
        "text": "https://item.jd.com/xxxx.html 华硕 RTX 5080 TUF 显卡 16G",
        "answers": ["游戏", "within_30", "high", "mid", "yes", "hedonic",
                    "up", "yes", "wait", "now", "wait"],
    },
    "drug": {
        "text": "布洛芬缓释胶囊 退烧止痛药 京东大药房",
        "answers": ["急用", "now", "mid"],
    },
    "phone": {
        "text": "iPhone 17 Pro 手机 256G",
        "answers": ["日常通讯", "none", "medium", "high", "no", "utilitarian",
                    "stable", "no", "now", "now", "now"],
    },
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", choices=list(SCRIPTS))
    ap.add_argument("--interactive", action="store_true")
    args = ap.parse_args()

    if args.interactive:
        text = input("粘贴商品链接或描述: ").strip()
        product = parse_product_text(text)
        if not product["category"]:
            name = input("没认出品类，请确认商品名: ").strip()
            cat = input("品类（显卡/手机/笔记本/游戏机/相机/家电/药品/医疗用品/基础食品）: ").strip()
            product = {"name": name, "category": cat, "source": "manual"}
        print("识别结果:", product["name"], "|", product["category"])
        qs, flow = build_questions(product)
        print("流程:", "必需（仅渠道比价）" if flow == "essential" else "完整时机问卷")

        def ask(q):
            print()
            print("Q:", q["text"])
            for i, o in enumerate(q.get("options", []), 1):
                label = o[0] if isinstance(o, tuple) else o
                print("  %d. %s" % (i, label))
            pick = input("选择（1-%d）: " % len(q.get("options", []))).strip()
            opts = q.get("options", [])
            return opts[int(pick) - 1][1] if isinstance(opts[int(pick) - 1], tuple) else opts[int(pick) - 1]
        profile = run_questionnaire(product, ask)
    elif args.case:
        case = SCRIPTS[args.case]
        product = parse_product_text(case["text"])
        if not product["category"]:
            product = {"name": case["text"][:30], "category": "药品", "source": "manual"}
        qs, flow = build_questions(product)
        print("== 剧本:", args.case, "| 品类:", product["category"], "| 流程:", flow, "| 问题屏数:", len(qs))
        ans_iter = iter(case["answers"])

        def ask(q):
            try:
                return next(ans_iter)
            except StopIteration:
                return "none"
        profile = run_questionnaire(product, ask)
    else:
        ap.print_help()
        return

    errs = validate_profile(profile)
    print("画像校验:", "通过" if not errs else errs)
    print(json.dumps(profile.to_dict(), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

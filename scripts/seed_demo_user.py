# -*- coding: utf-8 -*-
"""预置评委体验账号与典型决策快照（便于开箱即用体验与评审答辩）。
账号：reviewer / iris2026
运行：python scripts/seed_demo_user.py
"""
import os
import sys

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from iris.agent.pipeline import SCENARIOS, build_card
from iris.web import users as userstore

USERNAME = "reviewer"
PASSWORD = "iris2026"


def seed() -> None:
    userstore._ensure_dir()
    p = userstore._path(USERNAME)
    if os.path.exists(p):
        os.remove(p)

    userstore.register(USERNAME, PASSWORD)
    print("已创建测试账号: %s (密码: %s)" % (USERNAME, PASSWORD))

    # 1. 注入 3 张典型决策卡
    for item in SCENARIOS:
        sid = item["sku"]
        prof = dict(item["profile"])
        prof["product_ref"] = {"name": prof["name"], "category": prof["category"]}
        card = build_card(prof, sid)
        prod = {"name": prof["name"], "category": prof["category"], "source": "demo"}
        userstore.add_card(USERNAME, prod, sid, prof, card, note="[预置典型用例] " + item["label"])
        print("  + 注入历史快照: %s (%s)" % (item["label"], sid))

    # 2. 注入布洛芬必需品快照（空态比价闸门）
    med_prod = {"name": "布洛芬缓释胶囊", "category": "药品", "source": "demo"}
    med_prof = {"necessity": "essential", "purpose": "急用", "deadline": "now", "budget_tier": "mid"}
    userstore.add_card(USERNAME, med_prod, None, med_prof, None,
                       note="[预置典型用例] 药品必需闸门（时点不重要，渠道比价优先）")
    print("  + 注入历史快照: 布洛芬必需品闸门 (no_data)")

    # 3. 预置关注清单
    userstore.set_watch(USERNAME, "rtx5080-asus-tuf-mid")
    userstore.set_watch(USERNAME, "rtx5070-gigabyte-mid")
    print("  + 预置关注清单: RTX 5080 TUF, RTX 5070 技嘉")

    # 4. 预置品类画像
    userstore.save_answers(USERNAME, "显卡", SCENARIOS[0]["profile"])
    print("  + 预置显卡品类画像预填")
    print("评委体验账号就绪！")


if __name__ == "__main__":
    seed()

# -*- coding: utf-8 -*-
"""M5/M6 演示：用共享管线 iris/agent/pipeline.py 生成三画像全字段决策卡并打印摘要。

运行：python scripts/make_decision_demo.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from iris.agent.pipeline import SCENARIOS, build_card

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(ROOT, "data", "demo")
CARD_DIR = os.path.join(DEMO, "cards")


def main() -> None:
    os.makedirs(CARD_DIR, exist_ok=True)
    for item in SCENARIOS:
        sid = item["sku"]
        profile = dict(item["profile"])
        profile["product_ref"] = {"name": profile["name"],
                                  "category": profile["category"]}
        card = build_card(profile, sid)
        out = os.path.join(CARD_DIR, sid + ".json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(card, f, ensure_ascii=False, indent=1)
        st, p60, d = card["stats"], card["p1"]["60"], card["decision"]
        print("=" * 78)
        print("%s  [%s]" % (item["label"], sid))
        print("  现价 %d 元 | 365d 分位 %.2f | 90d 波动率分位 %.2f"
              % (st["last_price"], st["lookbacks"]["365"]["pct_position"],
                 st["volatility"]["pct_position"] or 0))
        p_str = ("P1(60d,5%%)= %.0f%%  CI[%.2f, %.2f]  n=%d"
                 % (p60["probability"] * 100, p60["ci95"][0], p60["ci95"][1],
                    p60["n"]) if p60["probability"] is not None
                 else "P1 样本不足 n=%d 仅方向 %s" % (p60["n"], p60["direction"]))
        print("  " + p_str)
        ws = (p60.get("wait_stats") or {})
        if ws:
            print("  等待策略统计：平均省 %.2f%% / 涨损 %.2f%%（同分位 %d 窗口）"
                  % (ws.get("saving_pct", 0), ws.get("loss_pct", 0),
                     ws.get("n_windows", 0)))
        print("  裁决：%s [%s]  P2(现在买最优)= %.0f%%  (网格 %d 情景, %s)"
              % (d["recommendation"], d["traffic_light"],
                 d["p2"]["probability"] * 100, d["p2"]["n_scenarios"],
                 d["p2"]["confidence"]))
        comp = d.get("decomposition")
        if comp:
            print("  分解: G=%.2f%%(¥%.0f) U=%.2f%%(¥%.0f) R=%.2f%%(¥%.0f) "
                  "buffer=%.2f%% net=%.2f%%(¥%.0f)"
                  % (comp["saving_pct"], comp["saving_yuan"], comp["u_pct"],
                     comp["u_yuan"], comp["r_pct"], comp["r_yuan"],
                     comp["buffer_pct"], comp["net_pct"], comp["net_yuan"]))
        sw = d.get("switch_to")
        print("  换购建议: %s" % ("无（无显著更优候选）" if not sw
                                   else "%s 省 ¥%d (%.1f%%) type=%s"
                                   % (sw["label"], sw["saving_abs"],
                                      sw["saving_pct"], sw["row_type"])))
        for c in d.get("conditions", [])[:6]:
            print("   · " + c["text"])
        print("  卡片已写:", out)


if __name__ == "__main__":
    main()

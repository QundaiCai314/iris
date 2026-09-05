# -*- coding: utf-8 -*-
"""用 demo 数据生成 P1 决策卡（M2.5 验收产物）与 P1 概览打印。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from iris.core.card import build_card, validate_card
from iris.core.p1 import forecast_windows
from iris.core.prices import load_all, load_events
from iris.core.stats import describe

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(ROOT, "data", "demo")
CARD_DIR = os.path.join(DEMO, "cards")


def main() -> None:
    products, skus, series = load_all(os.path.join(DEMO, "prices"), os.path.join(DEMO, "catalog.json"))
    os.makedirs(CARD_DIR, exist_ok=True)
    targets = ["rtx5080-asus-tuf-mid", "rtx5070-gigabyte-mid", "rtx5080-msi-ventus-entry-pdd"]
    print("P1 overview (60d default, drop=5%):")
    for sid in targets:
        ser = series[sid]
        st = describe(ser.points)
        fcw = forecast_windows(ser.points)
        card = build_card(skus[sid].product_id, sid, st["asof"], st, fcw)
        errs = validate_card(card)
        with open(os.path.join(CARD_DIR, sid + ".json"), "w", encoding="utf-8") as f:
            json.dump(card, f, ensure_ascii=False, indent=1)
        p60 = fcw["60"]
        p_str = ("%.1f%% [%s, %s]" % (p60["probability"] * 100, p60["ci95"][0], p60["ci95"][1])
                 if p60["probability"] is not None else "样本不足(n=%d, 仅方向:%s)"
                 % (p60["n"], p60["direction"]))
        print(" %-30s 现价 %-6d 365d分位 %-5.2f 波动率分位 %-5.2f  P1(60d,5%%)= %s"
              % (sid, st["last_price"], st["lookbacks"]["365"]["pct_position"],
                 st["volatility"]["pct_position"] or 0, p_str))
        if errs:
            print("  卡片校验错误:", errs)
        else:
            print("  卡片已写:", os.path.join(CARD_DIR, sid + ".json"))
    ev = load_events(os.path.join(DEMO, "events.json"))
    print("事件字典就绪: %d 条（M3 使用）" % len(ev))


if __name__ == "__main__":
    main()

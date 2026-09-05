# -*- coding: utf-8 -*-
"""M3 演示报告：demo 数据上的事件研究 + 生命周期代理 + 门控（M3.1-3.3 验收）。"""
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from iris.core.events import build_event_study
from iris.core.gate import check_gate
from iris.core.lifecycle import expect_price
from iris.core.prices import load_all, load_events
from iris.core.stats import describe

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(ROOT, "data", "demo")


def main() -> None:
    products, skus, series = load_all(os.path.join(DEMO, "prices"), os.path.join(DEMO, "catalog.json"))
    evs = load_events(os.path.join(DEMO, "events.json"))
    report = {"products": {}, "proxy_demo": None, "gate_demo": {}}

    # 1) promo pooling（品类级事件，自身路径）
    study_promo = build_event_study(series, skus, products, evs, "rtx5080", event_type="promo")
    print("== RTX 5080：大促事件 pooling（3 起：618-2025 / 双11-2025 / 618-2026）==")
    for h in ("30", "60", "90"):
        s = study_promo["promo"]["horizons"][h]
        print(" 事件后 %s 天平均相对起点 %+.2f%%  [%s]  n=%d"
              % (h, s["mean_pct"] or 0, s["ci95_pct"], s["n"]))

    # 2) launch 事件对照组差分（2025-11-01 supply 对 5080 相对 5070 系）
    study_launch = build_event_study(series, skus, products, evs, "rtx5080",
                                     event_type="launch")
    print("== RTX 5080：换代发布事件（对照组差分）==")
    for ev in study_launch.get("launch", {}).get("paths", []):
        print(" 事件 %s (%s) 路径点数 %d" % (ev["event_id"], ev["event_date"], ev["n_days"]))

    # 3) supply 事件差分（对照 = 5070ti+5070 中位）
    study_supply = build_event_study(series, skus, products, evs, "rtx5080",
                                     event_type="supply")
    print("== RTX 5080：供需事件（2025-11 行情启动）相对对照组的窗口==")
    for h in ("30", "60", "90"):
        s = study_supply.get("supply", {}).get("horizons", {}).get(h, {})
        if s and s["n"]:
            print(" 事件后 %s 天相对对照组 %+.2f%%  n=%d" % (h, s["mean_pct"], s["n"]))
    report["rtx5080"] = {"promo": study_promo["promo"]["horizons"],
                         "supply": study_supply.get("supply", {}).get("horizons")}

    # 4) 生命周期代理（新品演示：无历史数据的未来型号）
    prox = expect_price(8999, "2026-11-01", "2026-12-15", "gpu")
    print("== 生命周期代理：未上市新品示例（2026-11 上市，上市 1.5 个月后代理期望价）==")
    print(" 期望价约 %d 元（上市价 8999 x %.1f%%），proxy=%s" % (prox["expect_price"],
          prox["price_pct"] * 100, prox["proxy"]))
    report["proxy_demo"] = prox

    # 5) 门控
    st = describe(series["rtx5080-asus-tuf-mid"].points)
    g = check_gate(st["volatility"]["pct_position"], evs, "rtx5080", date(2026, 9, 3))
    print("== 门控（5080，2026-09-03）==")
    print(" abnormal=%s  波动率分位=%.2f  原因=%s" % (g["abnormal"],
          st["volatility"]["pct_position"] or 0, g["reasons"] or "无"))
    report["gate_demo"] = g

    with open(os.path.join(DEMO, "events_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print("报告已写: data/demo/events_report.json")


if __name__ == "__main__":
    main()

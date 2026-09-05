# -*- coding: utf-8 -*-
"""校准报告（M2.4 验收产物）：对 demo 各 SKU 滚动收集 (p, outcome) 并评估。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from iris.core.calib import run_report
from iris.core.prices import load_all

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(ROOT, "data", "demo")


def main() -> None:
    products, skus, series = load_all(os.path.join(DEMO, "prices"), os.path.join(DEMO, "catalog.json"))
    reports = {}
    for sid in sorted(series):
        ser = series[sid]
        rep = run_report(ser.points, label=sid)
        reports[sid] = rep
        if rep["n"] > 0 and rep["max_dev"] is not None:
            print("%-30s 校准样本 n=%-4d Brier=%.4f max|dev|=%.3f 降级=%s"
                  % (sid, rep["n"], rep["brier"], rep["max_dev"], rep["degraded"]))
        else:
            print("%-30s 校准样本 n=%d（不足以评估，流程已跑通）" % (sid, rep["n"]))
    with open(os.path.join(DEMO, "calib_report.json"), "w", encoding="utf-8") as f:
        json.dump(reports, f, ensure_ascii=False, indent=1)
    print("报告已写: data/demo/calib_report.json")


if __name__ == "__main__":
    main()

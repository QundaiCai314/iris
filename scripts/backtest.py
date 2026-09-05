# -*- coding: utf-8 -*-
"""M7.1 CLI：截断历史回测（实现见 iris/core/backtest.py）。

运行：python scripts/backtest.py [--every 14] [--out data/demo/backtest_report.json]
      python scripts/backtest.py --skus rtx5080-asus-tuf-mid --max-points-per-sku 2  # 快速调试

验收（TASK_PLAN M7.1）：报告含「回测 != 未来保证」免责声明；结果可复现（引擎确定性）。
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from iris.core.backtest import (DEFAULT_EVERY_DAYS, DEFAULT_MIN_FUTURE_DAYS,
                                DEFAULT_MIN_HISTORY_DAYS, run_backtest, render_summary)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(ROOT, "data", "demo")
DEFAULT_OUT = os.path.join(DEMO, "backtest_report.json")


def main() -> None:
    ap = argparse.ArgumentParser(description="Iris 截断历史回测（M7.1）")
    ap.add_argument("--every", type=int, default=DEFAULT_EVERY_DAYS,
                    help="asof 网格最小间隔（日历日，默认 %d）" % DEFAULT_EVERY_DAYS)
    ap.add_argument("--min-history", type=int, default=DEFAULT_MIN_HISTORY_DAYS,
                    help="asof 之前最少历史天数（默认 %d）" % DEFAULT_MIN_HISTORY_DAYS)
    ap.add_argument("--min-future", type=int, default=DEFAULT_MIN_FUTURE_DAYS,
                    help="asof 之后最少保留天数（默认 %d）" % DEFAULT_MIN_FUTURE_DAYS)
    ap.add_argument("--seed", type=int, default=20260905, help="元数据/扩展位（默认 20260905）")
    ap.add_argument("--skus", nargs="*", default=None, help="只测指定 SKU（默认全部）")
    ap.add_argument("--profiles", nargs="*", default=None,
                    choices=["gpu_high", "gpu_low", "gpu_pdd"], help="只测指定画像（默认全部）")
    ap.add_argument("--max-points-per-sku", type=int, default=None, help="每 SKU 最多 asof 点数（调试）")
    ap.add_argument("--out", default=DEFAULT_OUT, help="报告输出路径")
    args = ap.parse_args()

    report = run_backtest(os.path.join(DEMO, "prices"), os.path.join(DEMO, "catalog.json"),
                          every_days=args.every,
                          min_history_days=args.min_history,
                          min_future_days=args.min_future,
                          sku_ids=args.skus,
                          profile_keys=args.profiles,
                          seed=args.seed,
                          max_points_per_sku=args.max_points_per_sku)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(render_summary(report))
    print("报告已写: %s（%d 行明细）" % (args.out, len(report["rows"])))


if __name__ == "__main__":
    main()

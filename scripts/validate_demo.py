# -*- coding: utf-8 -*-
"""演示数据校验与概览（M1.2/M1.3 验收）：加载 -> 校验 -> 统计 -> 出 K 线 SVG。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from iris.core.prices import load_all, load_events, resample_ohlc, validate_all
from iris.core.svgk import kline_svg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(ROOT, "data", "demo")
PRICES_DIR = os.path.join(DEMO, "prices")

SKU_TITLES = {
    "rtx5080-asus-tuf-mid": "RTX 5080 ASUS TUF（最近180天 周K）",
    "rtx5070-gigabyte-mid": "RTX 5070 技嘉（最近180天 周K，涨势平缓对照）",
}


def main() -> None:
    products, skus, series = load_all(PRICES_DIR, os.path.join(DEMO, "catalog.json"))
    errs, warns = validate_all(products, skus, series)
    if errs:
        print("ERRORS:")
        for e in errs:
            print(" -", e)
        sys.exit(1)
    print("catalog: %d products, %d skus; series: %d" % (len(products), len(skus), len(series)))
    print("events:", len(load_events(os.path.join(DEMO, "events.json"))))
    print("warnings:", len(warns))
    for w in warns[:5]:
        print("  warn:", w)

    print()
    print("per-sku summary:")
    for sid in sorted(series):
        sku = skus[sid]
        ser = series[sid]
        pts = ser.points
        prices = [p.price for p in pts]
        last = prices[-1]
        win = prices[-365:]
        pct_pos = 0.0
        if win:
            pct_pos = sum(1 for v in win if v <= last) / len(win)
        d90 = (last - prices[-90]) / prices[-90] * 100
        print(" %-30s %-10s %-4s %5d点 %s..%s  现价 %d  365d分位 %.2f  近90d %+.1f%%"
              % (sid, sku.product_id, sku.channel, len(pts), pts[0].date, pts[-1].date,
                 last, pct_pos, d90))

    # 出 K 线（最近 180 天周线）
    for sid, fname in [("rtx5080-asus-tuf-mid", "kline_rtx5080_asus_mid.svg"),
                       ("rtx5070-gigabyte-mid", "kline_rtx5070_giga_mid.svg")]:
        if sid not in series:
            continue
        pts = series[sid].points[-180:]
        ohlc = resample_ohlc(pts, 7)
        out = os.path.join(DEMO, fname)
        kline_svg(SKU_TITLES.get(sid, sid), ohlc, out)
        print("kline ->", out, "(%d weekly bars)" % len(ohlc))


if __name__ == "__main__":
    main()

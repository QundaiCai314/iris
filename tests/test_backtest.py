# -*- coding: utf-8 -*-
"""M7.1 回测回归：确定性可复现 / 报告结构 / 截断等价（无前视）/ 标签窗口边界。"""
import os

from iris.agent import pipeline
from iris.core.backtest import future_low, run_backtest
from iris.core.models import PricePoint
from iris.core.p1 import forecast_windows
from iris.core.stats import describe

DEMO = os.path.join(pipeline.ROOT, "data", "demo")
PRICES = os.path.join(DEMO, "prices")
CATALOG = os.path.join(DEMO, "catalog.json")


def _series_of(sku_id):
    d = pipeline.load_demo()
    return d["series"][sku_id].points


def test_run_backtest_deterministic_and_reproducible():
    """同参数跑两次，输出逐字节一致（引擎确定性，无随机源）。"""
    kw = dict(price_dir=PRICES, catalog_path=CATALOG,
              sku_ids=["rtx5080-asus-tuf-mid"], profile_keys=["gpu_high"],
              max_points_per_sku=1)
    r1 = run_backtest(**kw)
    r2 = run_backtest(**kw)
    assert r1 == r2, "确定性引擎两次运行应完全一致"
    assert r1["n_rows"] >= 1
    assert r1["seed"] == 20260905


def test_report_structure_and_disclaimer():
    r = run_backtest(price_dir=PRICES, catalog_path=CATALOG,
                     sku_ids=["rtx5080-asus-tuf-mid"], profile_keys=["gpu_high"],
                     max_points_per_sku=1)
    for k in ("title", "version", "seed", "reproducibility", "disclaimer",
              "limits", "settings", "n_rows", "overall", "per_profile",
              "per_sku", "calibration", "rows"):
        assert k in r, "报告缺字段: %s" % k
    text = "".join(r["disclaimer"])
    assert "回测" in text and "未来保证" in text
    assert "synthetic-demo" in r["settings"]["data_note"]
    row = r["rows"][0]
    for k in ("sku_id", "asof", "last_price", "rec", "hit", "saving_pct", "p1_prob"):
        assert k in row, "missing key: %s" % k
    # 结果窗完整性：asof 与序列末尾至少保留 min_future_days(63)（剔除残缺窗）
    from datetime import date, timedelta
    from iris.core.stats import _d
    pts = _series_of(row["sku_id"])
    tail_gap = (_d(pts[-1]) - date.fromisoformat(row["asof"])).days
    assert tail_gap >= 63, "asof 后应保留完整 60 天结果窗，实际 %d 天" % tail_gap
    # 未来标签窗口：(asof, asof + wait_days] 内的最低价
    gap = (date.fromisoformat(row["fut_low_date"]) - date.fromisoformat(row["asof"])).days
    assert 0 < gap <= row["wait_days"], gap


def _dates_since(d0, n_days):
    from datetime import date, timedelta
    d = date.fromisoformat(d0)
    return [d + timedelta(days=k) for k in range(n_days)]


def test_future_low_respects_window_boundary():
    """窗 = 60 日历日：第 80 天的更低点不得计入；第 20 天低点须计入。"""
    pts = [PricePoint(date=dd.isoformat(), price=300 + k)
           for k, dd in enumerate(_dates_since("2026-01-01", 120))]
    pts[20] = PricePoint(date=pts[20].date, price=100)   # 窗内低点
    pts[80] = PricePoint(date=pts[80].date, price=50)    # 窗外更低点
    low, low_d, n = future_low(pts, 0, 60)
    assert low == 100 and n == 60, (low, low_d, n)


def test_truncated_series_equals_asof_engine():
    """截断子序列调用 == 引擎 asof_idx 语义（证明回测路径与引擎口径一致、无前视）。"""
    pts = _series_of("rtx5080-asus-tuf-mid")
    i = len(pts) // 2
    fc_trunc = forecast_windows(pts[:i + 1])
    fc_asof = forecast_windows(pts, asof_idx=i)
    assert fc_trunc == fc_asof, "截断调用与 asof_idx 调用结果应一致"
    st_trunc = describe(pts[:i + 1])
    st_asof = describe(pts, asof_idx=i)
    assert st_trunc == st_asof

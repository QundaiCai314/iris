# -*- coding: utf-8 -*-
"""M7.1 截断历史回测（walk-forward 样本外；红线 P4，详见 docs/redline-check.md）。

做什么：沿每个 SKU 价格序列取 asof 网格；每个 asof 只用其之前的数据
（describe / forecast_windows 以截断子序列调用；best_alt=None 不引入跨 SKU
现价横截面）跑决策引擎，得到 买/等 信号；再用 asof 之后「真实」未来窗
（窗口 = 画像允许的等待天数）度量结果：降价命中、平均节省、最坏情形。

口径与限制（详见报告 disclaimer / limits 字段）：
- 未来标签与 P1 wait_stats 同口径：窗内最低成交价（理想化：等满窗并以最低价成交）。
- 校准：P1(窗, 5%) 概率分桶 vs 实际「窗内降价 >=5%」频率；calib.py 为同族
  样本内自检（Brier），本回测是样本外策略层评估，两者互补。
- 事件相位修正（P1 v2）、替代矩阵 / 换购（跨 SKU 横截面）不在本回测范围。
- demo 数据为合成剧本（source=synthetic-demo）：结果只证明引擎在剧本内自洽，
  不承诺真实市场表现；回测 != 未来保证。

运行：python scripts/backtest.py（薄壳 CLI）
"""
from __future__ import annotations
from datetime import date
from typing import Dict, List, Optional, Tuple

from iris.agent.pipeline import SCENARIOS
from iris.core.decision import decide, pick_p1_window, wait_window_days
from iris.core.p1 import forecast_windows, wilson_ci
from iris.core.prices import load_all
from iris.core.stats import describe, _d

VERSION = "backtest-v1"
DEFAULT_EVERY_DAYS = 14        # asof 网格最小间隔（日历日）
DEFAULT_MIN_HISTORY_DAYS = 400 # asof 之前至少 400 天历史（stats/P1 稳定输入）
DEFAULT_MIN_FUTURE_DAYS = 63   # asof 之后保留 >= 63 天（60 天窗 + 缓冲）
DROP = 0.05                    # 降价命中阈值（与 P1 默认 drop 一致）
CAL_BINS = [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.0)]

DISCLAIMER = [
    "回测 != 未来保证：本回测在合成演示数据（source=synthetic-demo）内验证引擎",
    "的信号质量与校准一致性，不代表任何真实市场价格行为（总纲 2.6 / P4）。",
    "等待策略按「等满窗并以窗内最低价成交」记账（与 P1 wait_stats 一致），",
    "真实盯盘与跨渠道比价存在摩擦和成本，实际结果会差于该理想化口径。",
    "回测不改变、不搜索引擎参数：假设 A1-A7 数值仍待 B05 标定（D5），",
    "固定参数下评估，避免样本内过拟合。",
    "事件相位修正（P1 v2）与替代矩阵/换购（跨 SKU 现价横截面）未纳入本回测，",
    "覆盖范围仅为纵向时机维度。",
    "结果可复现：引擎为确定性计算（无随机源）；seed 字段为报告元数据与扩展位，",
    "输入与参数不变时输出逐字节一致。",
]

LIMITS = [
    "无前视：stats / P1 只使用 asof 之前的截断子序列，且 asof 与序列末尾之间",
    "保留完整结果窗；引擎内 P1 候选日与未来低价同样以 asof 为上限。",
    "画像 x SKU 为全组合：画像（需求参数）与 SKU（价格剧本）不要求语义匹配，",
    "测的是引擎对给定画像-行情组合裁决的稳健性。",
    "小样本桶（n < 5）不解释；P1 n < 30 记 insufficient、不给点概率（样本纪律）。",
]


def asof_candidates(points: List, every_days: int = DEFAULT_EVERY_DAYS,
                   min_history_days: int = DEFAULT_MIN_HISTORY_DAYS,
                   min_future_days: int = DEFAULT_MIN_FUTURE_DAYS) -> List[int]:
    """asof 网格：满足历史长度、未来窗完整，且间隔 >= every_days（日历日）。"""
    idxs: List[int] = []
    first_d = _d(points[0])
    last_d = _d(points[-1])
    for i, pt in enumerate(points):
        d = _d(pt)
        if (d - first_d).days < min_history_days:
            continue
        if (last_d - d).days < min_future_days:
            break
        if idxs and (d - _d(points[idxs[-1]])).days < every_days:
            continue
        idxs.append(i)
    return idxs


def future_low(points: List, i: int, window_days: int) -> Tuple[Optional[int], Optional[date], int]:
    """真实未来标签：i 之后 window_days 日历日内最低价（不含 i 当日）。
    返回 (low_price, low_date, n_points_in_window)。"""
    d0 = _d(points[i])
    low: Optional[int] = None
    low_d: Optional[date] = None
    n = 0
    for p in points[i + 1:]:
        dp = _d(p)
        if (dp - d0).days > window_days:
            break
        n += 1
        if low is None or p.price < low:
            low = p.price
            low_d = dp
    return low, low_d, n

def _saving_pct(last_price: int, fut_low: int) -> float:
    """等待策略净省（% 现价）：窗内最低价低于现价为正（省），高于为负（亏）。"""
    return round((last_price - fut_low) * 100.0 / last_price, 4)


def _median(xs: List[float]) -> Optional[float]:
    if not xs:
        return None
    s = sorted(xs)
    m = len(s) // 2
    return s[m] if len(s) % 2 else round((s[m - 1] + s[m]) / 2.0, 4)


def _agg_rows(rows: List[Dict]) -> Dict:
    """对一组行聚合（全部行 = 总体；也可按 rec / SKU / 画像过滤后调用）。
    口径：wait 行看「等待到窗内最低价成交」的节省分布与最坏情形；
    buy 行看「现在买后窗内仍出现 >=5% 更低点」的后悔率与错失幅度。"""
    n = len(rows)
    out: Dict = {"n": n}
    if not n:
        return out
    recs: Dict[str, int] = {}
    for r in rows:
        recs[r["rec"]] = recs.get(r["rec"], 0) + 1
    out["rec_counts"] = recs
    wait_rows = [r for r in rows if r["rec"] == "wait"]
    buy_rows = [r for r in rows if r["rec"] == "buy"]
    # 等待组
    w = None
    if wait_rows:
        sv = [r["saving_pct"] for r in wait_rows]
        hits = sum(1 for r in wait_rows if r["hit"])
        worse = max((r["saving_pct"] for r in wait_rows), default=0.0)
        w = {
            "n": len(wait_rows),
            "hit_rate": round(hits / len(wait_rows), 4),        # 窗内出现 >=5% 低点
            "avg_saving_pct": round(sum(sv) / len(sv), 4),      # 净省（含亏，%现价）
            "median_saving_pct": _median(sv),
            "positive_rate": round(sum(1 for x in sv if x > 0) / len(sv), 4),
            "worst_loss_pct": max(0.0, round(worse, 4)),        # 等亏最大幅度
        }
    out["wait"] = w
    # 买组
    b = None
    if buy_rows:
        reg = sum(1 for r in buy_rows if r["hit"])
        foregone = [max(0.0, r["saving_pct"]) for r in buy_rows]
        fine = sum(1 for r in buy_rows if not r["hit"])
        b = {
            "n": len(buy_rows),
            "regret_rate": round(reg / len(buy_rows), 4),       # 买后窗内仍出现 >=5% 低点
            "avg_foregone_pct": round(sum(foregone) / len(buy_rows), 4),
            "fine_rate": round(fine / len(buy_rows), 4),        # 无 >=5% 更低点
        }
    out["buy"] = b
    return out


def _bucket_of(prob: Optional[float]) -> str:
    if prob is None:
        return "insufficient"
    for lo, hi in CAL_BINS:
        if lo <= prob < hi:
            return "%.0f-%.0f%%" % (lo * 100, hi * 100)
    return "80-100%"


def _calibration(rows: List[Dict]) -> Dict:
    """P1 概率分桶 vs 实际命中频率（与引擎同用 Wilson CI 区间对照）。"""
    buckets: Dict[str, Dict] = {}
    order = ["0-20%", "20-40%", "40-60%", "60-80%", "80-100%", "insufficient"]
    for r in rows:
        k = _bucket_of(r["p1_prob"])
        d = buckets.setdefault(k, {"n": 0, "n_p": 0, "sum_p": 0.0, "hits": 0})
        d["n"] += 1
        if r["p1_prob"] is not None:
            d["sum_p"] += r["p1_prob"]; d["n_p"] += 1
        if r["hit"]:
            d["hits"] += 1
    bins = []
    for k in order:
        d = buckets.get(k)
        if not d or d["n"] < 5:
            if d and d["n"] > 0:
                bins.append({"bucket": k, "n": d["n"], "skipped": "n<5 不解释"});
            continue
        obs = d["hits"] / d["n"]
        avg_p = d["sum_p"] / d["n_p"] if d["n_p"] else None
        lo_ci, hi_ci = wilson_ci(d["hits"], d["n"])
        bins.append({
            "bucket": k,
            "n": d["n"],
            "avg_p1": round(avg_p, 4) if avg_p is not None else None,
            "n_p": d["n_p"],
            "obs_freq": round(obs, 4),
            "dev": round(obs - avg_p, 4) if avg_p is not None else None,
            "wilson_ci": [round(lo_ci, 4), round(hi_ci, 4)],
        })
    return {"bins": bins}


def run_backtest(price_dir: str, catalog_path: str,
                every_days: int = DEFAULT_EVERY_DAYS,
                min_history_days: int = DEFAULT_MIN_HISTORY_DAYS,
                min_future_days: int = DEFAULT_MIN_FUTURE_DAYS,
                sku_ids: Optional[List[str]] = None,
                profile_keys: Optional[List[str]] = None,
                seed: int = 20260905,
                max_points_per_sku: Optional[int] = None) -> Dict:
    """跑全量截断历史回测，返回报告字典（可复现、含免责与限制说明）。
    sku_ids / profile_keys / max_points_per_sku 供测试与局部调试缩小范围。"""
    products, skus, series = load_all(price_dir, catalog_path)
    sel_skus = [sid for sid in sorted(series)
                if not sku_ids or sid in set(sku_ids)]
    profs = [s for s in SCENARIOS
             if not profile_keys or s["key"] in set(profile_keys)]
    if not sel_skus:
        raise ValueError("没有可回测的 SKU 序列（price_dir 为空或 sku_ids 全不匹配）")
    if not profs:
        raise ValueError("没有可用画像（profile_keys 全不匹配）")
    rows: List[Dict] = []
    skipped = 0
    for sid in sel_skus:
        pts = series[sid].points
        cand = asof_candidates(pts, every_days, min_history_days, min_future_days)
        if max_points_per_sku:
            cand = cand[:max_points_per_sku]
        for i in cand:
            hist = pts[:i + 1]            # 截断：asof 及之前
            stats = describe(hist)        # asof 截面统计（只用截断序列）
            fcw = forecast_windows(hist)  # 30/60/180 窗 P1（只用截断序列）
            vol_pct = stats["volatility"]["pct_position"]
            for sc in profs:
                profile = dict(sc["profile"])
                wait_days = wait_window_days(profile)
                low, low_d, n_fut = future_low(pts, i, wait_days)
                if low is None or n_fut < wait_days:
                    skipped += 1           # 结果窗不完整（双保险）
                    continue
                dec = decide(profile, fcw, vol_pct, best_alt=None)
                p1fc = pick_p1_window(fcw, wait_days)
                last = pts[i].price
                decomp = dec.get("decomposition") or {}
                rows.append({
                    "sku_id": sid,
                    "product_id": skus[sid].product_id,
                    "profile": sc["key"],
                    "asof": _d(pts[i]).isoformat(),
                    "last_price": last,
                    "n_history": len(hist),
                    "wait_days": wait_days,
                    "rec": dec["recommendation"],
                    "light": dec["traffic_light"],
                    "confidence": dec["confidence"],
                    "net_pct": decomp.get("net_pct"),
                    "p1_window": str(wait_days),
                    "p1_prob": p1fc.get("probability"),
                    "p1_n": p1fc.get("n"),
                    "fut_low": low,
                    "fut_low_date": low_d.isoformat(),
                    "hit": bool(low <= last * (1.0 - DROP)),
                    "saving_pct": _saving_pct(last, low),
                })
    report: Dict = {
        "title": "Iris 截断历史回测报告（M7.1）",
        "version": VERSION,
        "generated": date.today().isoformat(),
        "seed": seed,
        "reproducibility": "确定性引擎（无随机源）：输入与参数不变时输出逐字节一致；"
                        "seed 为元数据/扩展位。",
        "disclaimer": DISCLAIMER,
        "limits": LIMITS,
        "settings": {
            "every_days": every_days,
            "min_history_days": min_history_days,
            "min_future_days": min_future_days,
            "drop": DROP,
            "p1_windows": [30, 60, 180],
            "decision_engine": "decide(best_alt=None)：替代/换购维度不在本回测",
            "profiles": [s["key"] for s in profs],
            "skus": sel_skus,
            "data_note": "synthetic-demo（合成剧本），非真实价格抓取",
        },
        "n_rows": len(rows),
        "skipped_incomplete": skipped,
        "overall": _agg_rows(rows),
        "per_profile": {k: _agg_rows([r for r in rows if r["profile"] == k])
                        for k in sorted({r["profile"] for r in rows})},
        "per_sku": {k: _agg_rows([r for r in rows if r["sku_id"] == k])
                   for k in sorted({r["sku_id"] for r in rows})},
        "calibration": _calibration(rows),
        "calibration_by_profile": {k: _calibration([r for r in rows if r["profile"] == k])
                                  for k in sorted({r["profile"] for r in rows})},
        "rows": rows,
    }
    return report


def _pct(x, nd=1):
    if x is None:
        return "--"
    return ("%." + str(nd) + "f%%") % x


def render_summary(rep: Dict) -> str:
    """控制台/文档用 Markdown 摘要（详细行数据在 JSON 报告）。"""
    out: List[str] = []
    o = rep["overall"]
    out.append("# %s" % rep["title"]);
    out.append("");
    out.append("- 设置：asof 间隔 >= %d 天 | 历史 >= %d 天 | 结果窗保留 >= %d 天 | 命中阈值 >=%.0f%% | seed=%d"
             % (rep["settings"]["every_days"], rep["settings"]["min_history_days"],
                rep["settings"]["min_future_days"], rep["settings"]["drop"] * 100, rep["seed"]));
    out.append("- 样本：%d 决策点（%d SKU x %d 画像），跳过不完整窗 %d 次"
             % (rep["n_rows"], len(rep["settings"]["skus"]),
                len(rep["settings"]["profiles"]), rep["skipped_incomplete"]));
    out.append("- 数据：%s" % rep["settings"]["data_note"]);
    out.append("");
    out.append("## 总体信号与结果分布");
    out.append("");
    w = o.get("wait");
    b = o.get("buy");
    out.append("| 组 | n | 关键指标 | 数值 |");
    out.append("| --- | --- | --- | --- |");
    out.append("| 建议=等 | %d | 命中率（窗内降价 >=5%%） | %s |"
             % (w["n"] if w else 0, _pct(w["hit_rate"] * 100) if w else "--"));
    out.append("| 建议=等 | %d | 平均净省（%%现价，负=等亏） | %s |"
             % (w["n"] if w else 0, _pct(w["avg_saving_pct"], 2) if w else "--"));
    out.append("| 建议=等 | %d | 节省为正的比例 | %s |"
             % (w["n"] if w else 0, _pct(w["positive_rate"] * 100) if w else "--"));
    out.append("| 建议=等 | %d | 最坏情形（等亏最大幅度） | %s |"
             % (w["n"] if w else 0, _pct(w["worst_loss_pct"], 2) if w else "--"));
    out.append("| 建议=买 | %d | 后悔率（买后窗内仍降价 >=5%%） | %s |"
             % (b["n"] if b else 0, _pct(b["regret_rate"] * 100) if b else "--"));
    out.append("| 建议=买 | %d | 错失均价（%%现价） | %s |"
             % (b["n"] if b else 0, _pct(b["avg_foregone_pct"], 2) if b else "--"));
    out.append("");
    out.append("### 分画像");
    out.append("");
    out.append("| 画像 | n | 等:买 | 等命中 | 等均净省 | 等最坏 | 买后悔 |");
    out.append("| --- | --- | --- | --- | --- | --- | --- |");
    for k in sorted(rep["per_profile"]):
        d = rep["per_profile"][k];
        dw = d.get("wait");
        db = d.get("buy");
        rc = d.get("rec_counts") or {};
        out.append("| %s | %d | %d:%d | %s | %s | %s | %s |"
                 % (k, d["n"], rc.get("wait", 0), rc.get("buy", 0),
                    _pct(dw["hit_rate"] * 100) if dw else "--",
                    _pct(dw["avg_saving_pct"], 2) if dw else "--",
                    _pct(dw["worst_loss_pct"], 2) if dw else "--",
                    _pct(db["regret_rate"] * 100) if db else "--"));
    out.append("");
    out.append("## P1 校准（样本外概率桶 vs 实际频率）");
    out.append("");
    out.append("| 桶 | n | 平均 P1 | 实际频率 | 偏差 | Wilson 95% |");
    out.append("| --- | --- | --- | --- | --- | --- |");
    for bd in rep["calibration"]["bins"]:
        if "skipped" in bd:
            out.append("| %s | %d | %s |" % (bd["bucket"], bd["n"], bd["skipped"]));
        else:
            dev_s = "--" if bd["dev"] is None else "%+.3f" % bd["dev"]
            out.append("| %s | %d | %s | %s | %s | %s-%s |"
                     % (bd["bucket"], bd["n"], _pct(bd["avg_p1"] * 100) if bd["avg_p1"] is not None else "--",
                        _pct(bd["obs_freq"] * 100), dev_s,
                        _pct(bd["wilson_ci"][0] * 100, 0), _pct(bd["wilson_ci"][1] * 100, 0)));
    out.append("");
    out.append("## 免责与限制");
    for line in rep["disclaimer"]:
        out.append("- " + line);
    out.append("");
    out.append("限制：");
    for line in rep["limits"]:
        out.append("- " + line);
    out.append("");
    return "\n".join(out)

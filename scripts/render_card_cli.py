# -*- coding: utf-8 -*-
"""M6.1 CLI 决策卡渲染：端到端路径的终端版完整卡片。

运行：
  python scripts/render_card_cli.py                      # 默认剧本 1（5080 高位）
  python scripts/render_card_cli.py --scenario gpu_low   # 剧本 2（5070 低位）
  python scripts/render_card_cli.py --interactive        # 粘贴文本 -> 画像问答 -> 出卡

结构：标题/元信息 -> K线 sparkline -> 价格统计 -> P1 三窗 -> 裁决/分解/P2 ->
事件摘要 -> 替代矩阵 -> 依据链。每个数字块标注 ref（口径出处，M6.1 验收：
抽查任意数字可指认来源）。
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from iris.agent.needs import build_questions, run_questionnaire
from iris.agent.pipeline import SCENARIOS, build_card, resolve_product

BARS = "▁▂▃▄▅▆▇█"


def sparkline(closes, width=60):
    """迷你走势：近 width 个周收盘价 -> 字符条。"""
    xs = closes[-width:]
    lo, hi = min(xs), max(xs)
    if hi - lo < 1e-9:
        return "".join(["▄"] * len(xs)), lo, hi
    return "".join(BARS[int((x - lo) / (hi - lo) * (len(BARS) - 1))] for x in xs), lo, hi


def pct1(x):
    return ("%.1f%%" % (x * 100)) if x is not None else "--"


def fmt_ci(ci):
    return "无（样本不足）" if not ci else "[%.2f, %.2f]" % (ci[0], ci[1])


def light_word(light):
    return {"green": "绿 · 买", "yellow": "黄 · 等/换", "red": "红 · 别现在买"}[light]


def render(card) -> None:
    meta, st = card["meta"], card["stats"]
    d, alt = card["decision"], card["alternatives"]
    print("=" * 78)
    print("IRIS 决策卡  |  %s" % alt["target"]["label"])
    print("  %s | 数据截至 %s | 引擎 v%s | %s"
          % (meta["product_id"], meta["asof_date"], meta["engine_version"],
             "【合成演示数据】" if "synthetic" in (card["evidence"][0]["ref"])
             else ""))
    line = "─" * 78
    print(line)

    # K 线 sparkline（近 60 周收盘）+ 现价
    closes = [w["close"] for w in card["kline"]]
    sp, lo, hi = sparkline(closes, 60)
    print("周线收盘（近 %d 周，满量程 %d ~ %d 元）：" % (len(sp), lo, hi))
    print("  " + sp)
    print("  现价 %d 元 | 90d 分位 %.2f | 365d 分位 %.2f | 730d 分位 %.2f | "
          "90d 波动率分位 %.2f   [ref: stats.lookbacks/volatility]"
          % (st["last_price"], st["lookbacks"]["90"]["pct_position"],
             st["lookbacks"]["365"]["pct_position"],
             st["lookbacks"]["730"]["pct_position"],
             st["volatility"]["pct_position"] or 0))
    print("  近 8 周 OHLC：")
    for w in card["kline"][-8:]:
        print("    %s  O %-6d H %-6d L %-6d C %-6d" %
              (w["date"], w["open"], w["high"], w["low"], w["close"]))
    print(line)

    # P1 双概率（并列展示：P1 客观频率 + P2 决策概率）
    p1 = card["p1"]
    print("P1 降价概率（未来 N 天降价 ≥5% 的历史频率）   [ref: p1.windows + R04]")
    for w in ("30", "60", "180"):
        fc = p1.get(w, {})
        prob = ("%.0f%%" % (fc["probability"] * 100)
                if fc.get("probability") is not None else "样本不足(仅方向 %s)"
                % fc.get("direction"))
        print("  窗口 %-4s: P1=%-8s CI95 %-14s n=%-4d 阈值=%s 元"
              % (w, prob, fmt_ci(fc.get("ci95")), fc.get("n"),
                 fc.get("threshold")))
    ws = (p1.get("60") or {}).get("wait_stats")
    if ws:
        print("  等待策略(60d 同分位 %d 窗口)：平均可省 %.2f%% / 涨价风险损失 %.2f%%"
              "   [ref: p1.60.wait_stats]" % (ws["n_windows"],
                                              ws["saving_pct"], ws["loss_pct"]))
    print(line)

    # P2 + 裁决 + 分解
    comp = d.get("decomposition")
    p2 = d["p2"]
    print("P2 = 现在买是 60 天视野内最优决策的概率  %.0f%%（%d 情景参数扰动）"
          % (p2["probability"] * 100, p2["n_scenarios"]))
    print("   [ref: decision.p2 + D5（扰动维：档位/期限/波动率/通胀预期/供需）]")
    print()
    print(">>> 裁决：%-6s  红绿灯：%s  (confidence=%s)"
          % (d["recommendation"], light_word(d["traffic_light"]),
             d["confidence"]))
    if comp:
        print("  分解（元/占现价%）   [ref: decision.decomposition + R05 §3/A1-A7]")
        print("    G 等待收益    : %8.0f 元 (%5.2f%%)" % (comp["saving_yuan"],
                                                          comp["saving_pct"]))
        print("    U 等待效用损失: %8.0f 元 (%5.2f%%)" % (comp["u_yuan"],
                                                          comp["u_pct"]))
        print("    R 等待风险    : %8.0f 元 (%5.2f%%)（含供需附加 %.2f%%）"
              % (comp["r_yuan"], comp["r_pct"], comp["supply_premium_pct"]))
        print("    buffer 缓冲   : %8.0f 元 (%5.2f%%)   [ref: 总纲 §1.2 (S,s)]"
              % (comp["buffer_yuan"], comp["buffer_pct"]))
        print("    net 净期望    : %8.0f 元 (%5.2f%%)  -> %s"
              % (comp["net_yuan"], comp["net_pct"],
                 "倾向等" if comp["net_pct"] > 0 else "倾向买"))
        print("    U 参数：月损失率 %.2f%%（强度x享乐x贴现档）  [ref: R05 §3]"
              % comp["params"]["usage_loss_monthly_pct"])
    if d.get("switch_to"):
        s = d["switch_to"]
        print("  换购候选：%s  现价 %d 元，省 ¥%d（%.1f%%）性能 %.0f%%"
              % (s["label"], s["price"], s["saving_abs"], s["saving_pct"],
                 s["bench_ratio"] * 100))
    print()
    print("条件句（自动生成，改参数即变）：")
    for i, c in enumerate(d.get("conditions", []), 1):
        print("  %d. [%s] %s" % (i, c["scenario"], c["text"]))
    print(line)

    # 事件日历
    ev = card.get("events") or {}
    print("事件日历   [ref: events.* + R01]")
    for t in ("promo", "supply", "launch"):
        s = ((ev.get(t) or {}).get("horizons") or {}).get("60")
        if s:
            print("  %-7s 历史 %d 起：60 天窗平均 %+.2f%%（CI %s，n<30 仅参考）"
                  % (t, s["n"], s["mean_pct"] or 0, fmt_ci(s["ci95_pct"])))
    for u in (ev.get("upcoming") or [])[:4]:
        extra = ""
        if u.get("summary_text"):
            extra = " —— " + u["summary_text"]
        print("  → %s  %s（%d 天后%s）%s" % (u["date"], u["title"],
              u["days_ahead"], "，超出 60 天主窗" if u["beyond_days"] else "",
              extra))
    print(line)

    # 替代矩阵
    print("替代矩阵（R03 降级配对；可量化=价差+属性，品牌溢价「值不值由你判断」）")
    hdr = "  %-9s %-14s %-5s %-4s %6s %8s %7s %6s %9s" % (
        "type", "label", "tier", "ch", "price", "save%", "bench", "per元", "满足需求")
    print(hdr)
    for r in alt["rows"]:
        mark = "★" if d.get("switch_to") and d["switch_to"]["sku_id"] == r["sku_id"] else " "
        print(" %s%-8s %-16s %-5s %-5s %6d %7.1f%% %5.1f%% %6.2f  %s" % (
            mark, "同型号" if r["row_type"] == "same_product" else "跨型号",
            r["sku_id"], r["tier"], r["channel"], r["price"], r["saving_pct"],
            r["bench_ratio"] * 100, r["per_yuan"],
            "是" if r["satisfies_need"] else "否"))
    print("  （每元性能=benchmark/千元价；跨型号按性能分对齐，绝对价差见 save%）"
          "   [ref: alternatives.rows + R03 §2-3]")
    print(line)
    print("依据链（证据）：")
    for i, e in enumerate(card.get("evidence", []), 1):
        print("  %d. [%s] %s" % (i, e["ref"], e["note"]))
    print(line)
    print("提示：以上数字全部来自合成演示数据；参数假设 A1-A7 待 B05 标定，"
          "可在 Web 版中调整重算。")


def interactive() -> None:
    from iris.agent.pipeline import match_sku
    text = input("粘贴商品链接或描述: ").strip()
    res = resolve_product(text)
    print("识别: %s | %s %s" % (res["product"]["name"], res["product"]["category"],
                                res["message"] or ""))
    if not res["product"]["category"]:
        name = input("手动确认商品名: ").strip()
        cat = input("品类: ").strip() or "显卡"
        res["product"] = {"name": name, "category": cat, "source": "manual"}
        res["sku_id"] = match_sku(name) if cat == "显卡" else None
        if not res["sku_id"]:
            print("（demo 库仅显卡 5080/5070Ti/5070；无价格数据只演示问卷与闸门）")
    product = res["product"]
    qs, flow = build_questions(product)
    print("流程: %s（%d 屏）" % ("必需闸门" if flow == "essential" else "完整时机问卷",
                              len(qs)))

    def ask(q):
        print()
        print("Q:", q["text"])
        for i, o in enumerate(q.get("options", []), 1):
            label = o[0] if isinstance(o, tuple) else o
            print("  %d. %s" % (i, label))
        opts = q.get("options", [])
        while True:
            pick = input("选择(1-%d): " % len(opts)).strip()
            if pick.isdigit() and 1 <= int(pick) <= len(opts):
                break
        o = opts[int(pick) - 1]
        return o[1] if isinstance(o, tuple) else o

    profile = run_questionnaire(product, ask)
    if res["sku_id"] is None:
        print()
        print("画像（流程演示）：", profile.to_dict())
        print("结论：%s 商品无 demo 价格数据 -> %s"
              % (product["category"], "必需品类：直接买，只做渠道比价（R05 §1）"
                 if profile.necessity == "essential"
                 else "可选品类：需接入价格库后出量化卡"))
        return
    card = build_card(profile.to_dict(), res["sku_id"])
    render(card)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", choices=[s["key"] for s in SCENARIOS],
                    default="gpu_high")
    ap.add_argument("--interactive", action="store_true")
    args = ap.parse_args()
    if args.interactive:
        interactive()
        return
    item = next(s for s in SCENARIOS if s["key"] == args.scenario)
    profile = dict(item["profile"])
    print("场景：%s -> %s\n" % (item["label"], item["sku"]))
    render(build_card(profile, item["sku"]))


if __name__ == "__main__":
    main()

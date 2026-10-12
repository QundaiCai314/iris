# -*- coding: utf-8 -*-
"""真实实用性全面检测脚本：
1. 真实大模型（StepFun）在复杂日常问法下的语义提取质量与鲁棒性
2. 真实耐用品价格库（iPhone 15 Pro / RTX 4080 / PS5）在不同用户真实画像下的决策差异度
3. 假设即时重算（期限修改/预算调整）的因果响应
4. 计量经济学与行为金融学输出的人话可读性与数值合理性
5. 极限/边界条件测试（库外商品、必需药品、冲突条件）
"""
import os
import sys
import json
import time

# 确保 UTF-8 终端
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from iris.agent.pipeline import resolve_product, build_card, load_demo
from iris.agent.needs import build_questions, run_questionnaire
from iris.llm.gateway import ModelGateway
from iris.llm.semantic import parse_product_semantic

def run_usability_audit():
    print("======================================================================")
    print("IRIS 鸢尾 · 项目真实实用性与综合能力全量体检报告")
    print("======================================================================\n")

    # ---------------- 维度 1: 真实大模型在线语义解析 ----------------
    print("【维度 1：自然语言口语化输入与 StepFun 大模型语义抽取】")
    gw = ModelGateway()
    print("  StepFun 实时网关在线状态:", gw.is_available("reasoning"))

    queries = [
        ("自然口语显卡", "马上要读研了，导师让我买张华硕4080显卡做深度学习实验，现在买划算不？"),
        ("自然口语手机", "想入手一台苹果iPhone 15 Pro 256G，现在买还是等下半年？"),
        ("自然口语主机", "索尼PS5国行光驱版打黑神话，现在2899要不要下手？"),
        ("电商直接链接", "https://item.jd.com/100068328148.html 索尼PlayStation 5"),
        ("库外数码耐用品", "大疆 Mini 4 Pro 无人机，下个月去西藏旅游想买"),
        ("家庭刚需药品", "家里老人急需降压药硝苯地平片控压，快吃完了")
    ]

    for tag, q in queries:
        t0 = time.time()
        res = resolve_product(q)
        lat = (time.time() - t0) * 1000
        p = res["product"]
        sku = res["sku_id"]
        hit = res["catalog_hit"]
        print(f"\n  [测试项: {tag}] (耗时 {lat:.1f}ms)")
        print(f"  用户原话: \"{q}\"")
        print(f"  -> 识别商品名: {p.get('name')}")
        print(f"  -> 识别品类:   {p.get('category')} (来源: {p.get('source')})")
        print(f"  -> 匹配SKU:    {sku or '（未入库）'}")
        print(f"  -> 可出量化卡: {'✓ 是' if hit else '✗ 否（转纯画像/闸门流程）'}")
        if res.get("message"):
            print(f"  -> 引导说明:   {res['message']}")

    # ---------------- 维度 2: 个性化差异与科学性（同一商品不同画像） ----------------
    print("\n\n" + "="*70)
    print("【维度 2：同品不同人决策差异检验（以真实 RTX 4080 为例）】")
    print("测试目标：检验系统是否像真正量化顾问一样，根据最晚期限与使用强度给出截然不同的建议。")

    # 画像 A: 实验室科研急用（高使用强度、下周必须投入实验、不可等、预算充足）
    profile_researcher = {
        "name": "华硕 TUF RTX 4080",
        "category": "显卡",
        "purpose": "AI / 跑模型",
        "deadline": "within_30",          # 1个月内必须用
        "usage_intensity": "high",         # 每天重度跑
        "budget_tier": "flexible",
        "alt_acceptable": "no",            # 指定此卡
        "hedonic": "utilitarian",          # 生产力工具（非享乐品）
        "wait_tier": "low",                # 不愿多等
        "price_view": "stable",
        "supply_news": "no"
    }

    # 画像 B: 价格敏感型玩家（游戏娱乐、无硬性截止期、每天轻度玩、愿意等大促打折）
    profile_gamer = {
        "name": "华硕 TUF RTX 4080",
        "category": "显卡",
        "purpose": "游戏",
        "deadline": "none",               # 可以无限等
        "usage_intensity": "low",         # 玩得少
        "budget_tier": "low",             # 预算紧
        "alt_acceptable": "yes",          # 接受平替
        "hedonic": "hedonic",             # 纯享乐
        "wait_tier": "high",              # 高度愿等折扣
        "price_view": "down",             # 预期还会降
        "supply_news": "no"
    }

    card_a = build_card(profile_researcher, "rtx4080-asus-tuf-jd")
    card_b = build_card(profile_gamer, "rtx4080-asus-tuf-jd")

    dec_a = card_a["decision"]
    dec_b = card_b["decision"]

    print("\n  ▶ 真实科研急用画像（生产力工具·高频使用·不可等）：")
    print(f"     - 最终裁决: [{dec_a['recommendation'].upper()}] (信号灯: {dec_a['traffic_light']})")
    print(f"     - 大白话结论: {dec_a['plain_language'].get('text')}")
    print(f"     - 现在买最优概率 (P2): {dec_a['p2']['probability']*100:.1f}%")
    print(f"     - 等待期望降价 G: {dec_a['decomposition']['saving_pct']:.2f}%")
    print(f"     - 效用损失扣减 U: {dec_a['decomposition']['u_pct']:.2f}% (等待成本高)")
    print(f"     - 风险与缓冲 R+Buf: {dec_a['decomposition']['r_pct'] + dec_a['decomposition']['buffer_pct']:.2f}%")
    print(f"     - 净等待期望收益: {dec_a['decomposition']['net_pct']:.2f}%")

    print("\n  ▶ 休闲玩家观望画像（享乐品·低频使用·可等可换）：")
    print(f"     - 最终裁决: [{dec_b['recommendation'].upper()}] (信号灯: {dec_b['traffic_light']})")
    print(f"     - 大白话结论: {dec_b['plain_language'].get('text')}")
    print(f"     - 现在买最优概率 (P2): {dec_b['p2']['probability']*100:.1f}%")
    print(f"     - 等待期望降价 G: {dec_b['decomposition']['saving_pct']:.2f}%")
    print(f"     - 效用损失扣减 U: {dec_b['decomposition']['u_pct']:.2f}% (等待成本低)")
    print(f"     - 风险与缓冲 R+Buf: {dec_b['decomposition']['r_pct'] + dec_b['decomposition']['buffer_pct']:.2f}%")
    print(f"     - 净等待期望收益: {dec_b['decomposition']['net_pct']:.2f}%")

    # ---------------- 维度 3: 真实商品计量模型表现（iPhone 15 Pro） ----------------
    print("\n\n" + "="*70)
    print("【维度 3：真实电商数据在计量经济与行为金融模型的真实输出（iPhone 15 Pro 360天）】")
    card_iphone = build_card({
        "name": "iPhone 15 Pro 256G",
        "category": "手机",
        "purpose": "日常通讯",
        "deadline": "within_90",
        "usage_intensity": "medium",
        "wait_tier": "mid"
    }, "iphone15pro-256g-jd")

    ou = card_iphone["stats"].get("mean_reversion", {})
    cpt = card_iphone["decision"]["decomposition"].get("prospect_theory", {})
    p1_60 = card_iphone["p1"].get("windows", {}).get("60", {})
    km = p1_60.get("survival_analysis") or {}

    last_price = card_iphone["stats"]["last_price"]
    print(f"  当前追踪价格: {last_price} 元 (截至: {card_iphone['stats']['asof']})")
    print(f"  1. OU 均值回归拟合:")
    print(f"     - 长期均衡中枢: {ou.get('equilibrium_price')} 元")
    print(f"     - 偏离中枢差额: {ou.get('current_deviation_yuan')} 元 ({ou.get('current_deviation_pct')}%)")
    print(f"     - 回归半衰期:   {ou.get('half_life_days')} 天 (解读：当前价差预期衰减一半的周期)")
    print(f"     - 均值回归特征: {'✓ 具备' if ou.get('is_mean_reverting') else '✗ 不具备（单边下行或随机游走）'}")
    print(f"     - 模型诊断提示: {ou.get('note')}")

    print(f"\n  2. CPT 累积前景理论心理折价 (Tversky & Kahneman):")
    print(f"     - 客观期望金额: {cpt.get('objective_expected_yuan')} 元")
    print(f"     - 心理确定性等价 (CE): {cpt.get('certainty_equivalent_yuan')} 元")
    print(f"     - 损失厌恶心理折价: {cpt.get('loss_aversion_wedge_yuan')} 元 (2.25倍放大涨价焦虑)")
    print(f"     - 行为建议: {cpt.get('behavior_advice')}")

    print(f"\n  3. 降价窗口持续时间统计 (Survival Duration):")
    if km and km.get("median_days_to_drop") is not None:
        print(f"     - 历史降价突破中位天数: {km.get('median_days_to_drop')} 天 (IQR区间: {km.get('iqr_days')} 天)")
        print(f"     - 样本命中次数: {km.get('n_drop_events')} 次")
        print(f"     - 口径说明: {km.get('citation')}")
    else:
        print(f"     - 持续期数据: 样本窗口内未发生降价或样本不足")

    # ---------------- 维度 4: 极端边界测试（刚需药品闸门） ----------------
    print("\n\n" + "="*70)
    print("【维度 4：边界安全测试（刚需医疗药品与必需闸门）】")
    p_drug = {"name": "硝苯地平片", "category": "药品", "source": "text"}
    qs, flow = build_questions(p_drug)
    print(f"  识别药品进入流程: {flow} (预期: essential 必需闸门，不跑时机等待模型)")
    print(f"  下发问卷题目数:   {len(qs)} 题 (跳过所有等待贴现与促销博弈题)")

    print("\n" + "="*70)
    print("综合体检执行完毕。")
    print("======================================================================")

if __name__ == "__main__":
    run_usability_audit()

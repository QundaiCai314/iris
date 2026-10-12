# -*- coding: utf-8 -*-
"""基于 LLM 的语义增强与 Agent 澄清（M4.3 实装）。
具备双模自适应能力：
- 有可用模型/API Key：执行少样本 Prompt 语义精准解析与自然语言澄清；
- 无 API Key 或调用失败：返回 None，由上层管道平滑使用确定性规则树兜底。
"""
from __future__ import annotations

import json
import logging
import re
from typing import Dict, Optional

from iris.core.decision import BANNED_WORDS
from iris.llm.gateway import get_gateway

logger = logging.getLogger("iris.llm")


PARSE_SYSTEM_PROMPT = """你是一个电商与消费品量化分析助理。
请从用户输入的商品链接或描述中提取结构化信息，输出纯 JSON 格式（不要包含任何 markdown 标记或额外解释）：
{
  "name": "标准商品型号名称，例如 '华硕 TUF-RTX5080-O16G-GAMING' 或 '布洛芬缓释胶囊'，若非商品则设为 null",
  "category": "品类标准词（显卡、手机、笔记本、游戏机、家电、相机、药品、医疗用品、基础食品），若非明确商品则设为 null",
  "brand": "品牌名（如 华硕、苹果、联想、中美史克等），未知则写 null",
  "is_essential": true 或 false（是否为药品、急救医疗、基础口粮等无弹性必需品）
}
注意：若用户输入纯闲聊、天气、非商品文本，category 与 name 必须输出 null，绝不可强行假定！"""


def _clean_json_str(text: str) -> str:
    """清理模型可能返回的 markdown 块。"""
    t = text.strip()
    if t.startswith("```"):
        lines = t.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    return t


def parse_product_semantic(text: str) -> Optional[Dict]:
    """尝试使用 LLM 解析商品链接/描述；无可用模型或解析失败时返回 None。"""
    gw = get_gateway()
    if not gw.is_available("reasoning"):
        return None

    messages = [
        {"role": "system", "content": PARSE_SYSTEM_PROMPT},
        {"role": "user", "content": f"商品输入文本：{text}"},
    ]

    res = gw.complete(messages, route_name="reasoning", temperature=0.1, max_tokens=1024)
    if not res or not res.get("content"):
        return None

    try:
        raw_json = _clean_json_str(res["content"])
        data = json.loads(raw_json)
        cat = data.get("category")
        if not cat or cat in ("其他", "未知", "null", "None"):
            return None
        return {
            "name": data.get("name") or text[:30],
            "category": cat,
            "brand": data.get("brand"),
            "is_essential": bool(data.get("is_essential")),
            "source": f"llm:{res.get('model')}",
        }
    except Exception as e:
        logger.warning("LLM 语义解析 JSON 失败: %s, 原始输出: %s", e, res.get("content"))
        return None


def explain_decision_semantic(card: Dict, profile: Dict) -> Optional[str]:
    """利用 LLM 生成定制化、高共情的专家建议解读（经红线词过滤）。"""
    gw = get_gateway()
    if not gw.is_available("reasoning"):
        return None

    dec = card.get("decision", {})
    pl = dec.get("plain_language", {})
    decomp = dec.get("decomposition", {})

    prompt = f"""商品：{profile.get('name', '商品')}（品类：{profile.get('category')}）
用户用途：{profile.get('purpose', '日常')}，最晚期限：{profile.get('deadline', 'none')}
决策裁决：{dec.get('recommendation')}（红绿灯：{dec.get('traffic_light')}）
P2最优概率：{int((dec.get('p2', {}).get('probability') or 0)*100)}%
原大白话结论：{pl.get('text')}
净等待期望：{decomp.get('net_pct')}%

【执行规范】：
1. 防迎合规范（Anti-Sycophancy）：严禁奉承讨好用户（禁说'您说得对'、'完全支持'），必须保持独立量化裁判立场，包含机会成本与反事实对冲；
2. 金融事实与宏观政策（Financial Grounding）：结合中国提振消费与以旧换新政策导向，客观分析；
3. 严格红线：严禁出现承诺词与绝对保证词。请用客观专业的语气写 80-120 字的决策解读。"""

    messages = [
        {"role": "system", "content": "你是一位客观严谨的量化消费决策顾问，严守防迎合与金融事实核查红线。"},
        {"role": "user", "content": prompt},
    ]
    res = gw.complete(messages, route_name="reasoning", temperature=0.3, max_tokens=250)
    if not res or not res.get("content"):
        return None

    text = res["content"].strip()
    # 红线词过滤检查
    for w in BANNED_WORDS:
        if w in text:
            return None  # 违规直接抛弃，降级回原生大白话
    return text

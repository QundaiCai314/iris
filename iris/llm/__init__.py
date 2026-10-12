# -*- coding: utf-8 -*-
"""多模型网关与 LLM 语义增强（D2 架构落地，支持 OpenAI / 智谱 / DeepSeek）。
提供具备候选链降级与规则平滑兜底的双模 Agent 运行时。
"""
from iris.llm.client import OpenAICompatClient
from iris.llm.gateway import ModelGateway, get_gateway
from iris.llm.semantic import explain_decision_semantic, parse_product_semantic

__all__ = [
    "OpenAICompatClient",
    "ModelGateway",
    "get_gateway",
    "parse_product_semantic",
    "explain_decision_semantic",
]

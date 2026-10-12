# -*- coding: utf-8 -*-
"""多模型路由网关与候选链降级（D2 架构落地）。
配置从 config/models.json（或 config/models.example.json 兜底）读取。
环境变量注入密钥：IRIS_OPENAI_API_KEY / IRIS_ZHIPU_API_KEY / IRIS_DEEPSEEK_API_KEY
也可通用 OPENAI_API_KEY / OPENAI_BASE_URL。
"""
from __future__ import annotations

import json
import logging
import os
from typing import Dict, List, Optional, Tuple

from iris.llm.client import OpenAICompatClient

logger = logging.getLogger("iris.llm")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_PATH = os.path.join(ROOT, "config", "models.json")
EXAMPLE_CONFIG_PATH = os.path.join(ROOT, "config", "models.example.json")


def load_dotenv_if_present() -> None:
    env_file = os.path.join(ROOT, ".env")
    if os.path.exists(env_file):
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k and k not in os.environ:
                        os.environ[k] = v
        except Exception:
            pass


load_dotenv_if_present()


def load_config() -> Dict:
    path = CONFIG_PATH if os.path.exists(CONFIG_PATH) else EXAMPLE_CONFIG_PATH
    if not os.path.exists(path):
        return {"providers": {}, "models": {}, "routes": {}}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class ModelGateway:
    """具备候选链降级（Fallback Chain）与双模（在线/离线规则）切换的 LLM 网关。"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or load_config()

    def get_provider_client(self, provider_name: str) -> Optional[Tuple[OpenAICompatClient, str]]:
        """获取 provider 客户端与默认配置。如果缺少 API Key 返回 None。"""
        providers = self.config.get("providers", {})
        p_cfg = providers.get(provider_name)
        if not p_cfg:
            # 兼容标准通用环境变量
            if provider_name == "openai":
                key = os.environ.get("OPENAI_API_KEY")
                base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
                if key:
                    return OpenAICompatClient(base, key, 30.0), "openai"
            return None

        env_var = p_cfg.get("api_key_env", "")
        api_key = (
            p_cfg.get("api_key")
            or (os.environ.get(env_var) if env_var else None)
            or (os.environ.get("OPENAI_API_KEY") if provider_name == "openai" else None)
            or (os.environ.get("IRIS_STEPFUN_API_KEY") if provider_name == "stepfun" else None)
        )
        if not api_key:
            return None

        base_url = p_cfg.get("base_url") or "https://api.openai.com/v1"
        timeout_s = float(p_cfg.get("timeout_s", 30))
        return OpenAICompatClient(base_url, api_key, timeout_s), provider_name

    def is_available(self, route_name: str = "reasoning") -> bool:
        """检查指定路由是否有任一可用模型（拥有对应 API Key）。"""
        routes = self.config.get("routes", {})
        chain = routes.get(route_name, {}).get("chain", [])
        models = self.config.get("models", {})
        for model_name in chain:
            m_cfg = models.get(model_name)
            if not m_cfg:
                continue
            prov = m_cfg.get("provider")
            if prov and self.get_provider_client(prov) is not None:
                return True
        return False

    def complete(
        self,
        messages: List[Dict[str, str]],
        route_name: str = "reasoning",
        temperature: float = 0.2,
        max_tokens: Optional[int] = 1024,
    ) -> Optional[Dict]:
        """沿候选链尝试生成，第一个成功的返回结果，全部失败或无 Key 返回 None（触发规则兜底）。"""
        routes = self.config.get("routes", {})
        chain = routes.get(route_name, {}).get("chain", [])
        models = self.config.get("models", {})

        errors = []
        for model_name in chain:
            m_cfg = models.get(model_name)
            if not m_cfg:
                continue
            prov = m_cfg.get("provider")
            res = self.get_provider_client(prov)
            if res is None:
                continue  # 无 key，跳往下一个候选

            client, _ = res
            try:
                resp = client.chat_completion(
                    model=model_name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                choices = resp.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "")
                    return {
                        "content": content,
                        "model": model_name,
                        "provider": prov,
                        "usage": resp.get("usage", {}),
                    }
            except Exception as e:
                logger.warning("模型 %s 调用失败，尝试候选链降级: %s", model_name, e)
                errors.append(f"{model_name}: {e}")

        if errors:
            logger.info("候选链全部失败: %s", "; ".join(errors))
        return None


# 单例默认网关
_default_gateway: Optional[ModelGateway] = None


def get_gateway() -> ModelGateway:
    global _default_gateway
    if _default_gateway is None:
        _default_gateway = ModelGateway()
    return _default_gateway

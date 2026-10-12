# -*- coding: utf-8 -*-
"""纯标准库 OpenAI 兼容 HTTP 客户端（零外部依赖）。
支持 OpenAI、智谱 GLM、DeepSeek 等遵循 OpenAI /v1/chat/completions 协议的服务商。
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Dict, List, Optional


class OpenAICompatClient:
    """基于 urllib.request 的轻量客户端，免去 requests/httpx 等重依赖。"""

    def __init__(self, base_url: str, api_key: str, timeout_s: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_s = timeout_s

    def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: Optional[int] = 1024,
        response_format: Optional[Dict] = None,
    ) -> Dict:
        """发送 /chat/completions 请求并返回字典。"""
        url = f"{self.base_url}/chat/completions"
        payload: Dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if response_format:
            payload["response_format"] = response_format

        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "Iris-Agent/0.3.0",
        }

        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"HTTP {e.code} from {url}: {err_msg}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Network error connecting to {url}: {e.reason}") from e

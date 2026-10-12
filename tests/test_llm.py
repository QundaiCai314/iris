# -*- coding: utf-8 -*-
"""M4.3 LLM 模块单测：客户端结构、网关候选链降级、无 key 兜底、红线词拦截。"""
import io
import json
from unittest.mock import MagicMock, patch

from iris.llm.client import OpenAICompatClient
from iris.llm.gateway import ModelGateway, get_gateway
from iris.llm.semantic import explain_decision_semantic, parse_product_semantic


def test_client_init():
    client = OpenAICompatClient("https://api.openai.com/v1", "test-key", 15.0)
    assert client.base_url == "https://api.openai.com/v1"
    assert client.api_key == "test-key"
    assert client.timeout_s == 15.0


def test_gateway_config():
    gw = get_gateway()
    assert "providers" in gw.config
    assert "routes" in gw.config
    assert "reasoning" in gw.config["routes"]


def test_gateway_fallback_no_keys(monkeypatch):
    monkeypatch.delenv("IRIS_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("IRIS_ZHIPU_API_KEY", raising=False)
    monkeypatch.delenv("IRIS_DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("IRIS_STEPFUN_API_KEY", raising=False)
    monkeypatch.delenv("STEPFUN_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    gw = ModelGateway()
    assert gw.is_available("reasoning") is False
    res = gw.complete([{"role": "user", "content": "hello"}])
    assert res is None
    # 语义解析在无 key 时平滑返回 None，不抛出异常
    assert parse_product_semantic("随便一个商品") is None


def test_gateway_mock_completion(monkeypatch):
    monkeypatch.setenv("IRIS_OPENAI_API_KEY", "mock-openai-key")
    gw = ModelGateway()

    mock_resp_payload = {
        "id": "chatcmpl-123",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": '{"name": "iPad Pro", "category": "平板电脑", "is_essential": false}'},
                "finish_reason": "stop",
            }
        ],
        "usage": {"total_tokens": 42},
    }

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(mock_resp_payload).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("iris.llm.client.urllib.request.urlopen", return_value=mock_resp):
        res = gw.complete([{"role": "user", "content": "test"}], route_name="reasoning")
        assert res is not None
        assert "iPad Pro" in res["content"]
        assert res["usage"]["total_tokens"] == 42


def test_banned_words_filter_in_semantic_explain(monkeypatch):
    monkeypatch.setenv("IRIS_OPENAI_API_KEY", "mock-openai-key")
    gw = ModelGateway()

    # 模拟大模型给出了包含红线违规词“保证必跌”的回复
    mock_resp_payload = {
        "choices": [
            {
                "message": {"role": "assistant", "content": "这款显卡我向你保证必跌，绝对不要现在买！"}
            }
        ]
    }
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(mock_resp_payload).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    card = {
        "decision": {
            "recommendation": "wait",
            "traffic_light": "yellow",
            "plain_language": {"text": "建议先等一等"},
        }
    }
    profile = {"name": "RTX 5080", "category": "显卡"}

    with patch("iris.llm.client.urllib.request.urlopen", return_value=mock_resp):
        with patch("iris.llm.semantic.get_gateway", return_value=gw):
            # 违规词必须被拦截，返回 None
            explanation = explain_decision_semantic(card, profile)
            assert explanation is None

import json
from unittest.mock import patch

import requests

from trading_mcp.execution.config import ExecutionConfig
from trading_mcp.execution.llm_advisor import LLMAdvisor


def _make_config(**overrides) -> ExecutionConfig:
    defaults = dict(openrouter_api_key="test-key", llm_model="qwen/qwen3-30b-a3b-instruct-2507")
    defaults.update(overrides)
    return ExecutionConfig(**defaults)


class _FakeResponse:
    def __init__(self, payload: dict, status: int = 200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")

    def json(self):
        return self._payload


def _openrouter_payload(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}]}


def test_decide_parses_valid_json_response():
    config = _make_config()
    advisor = LLMAdvisor(config)

    content = json.dumps({"direction": "LONG_ENTRY", "confidence": 0.8, "reasoning": "Trend kuat + berita positif"})
    with patch("trading_mcp.execution.llm_advisor.requests.post", return_value=_FakeResponse(_openrouter_payload(content))):
        decision = advisor.decide("BTC/USDT", 50000.0, "BULLISH", 7, ["EMA aligned"], [])

    assert decision.direction == "LONG_ENTRY"
    assert decision.confidence == 0.8
    assert "positif" in decision.reasoning


def test_decide_extracts_json_wrapped_in_extra_text():
    config = _make_config()
    advisor = LLMAdvisor(config)

    content = 'Here is my answer:\n{"direction": "EXIT", "confidence": 0.6, "reasoning": "Bearish reversal"}\nThanks.'
    with patch("trading_mcp.execution.llm_advisor.requests.post", return_value=_FakeResponse(_openrouter_payload(content))):
        decision = advisor.decide("BTC/USDT", 50000.0, "BEARISH", 2, [], [])

    assert decision.direction == "EXIT"


def test_decide_falls_back_to_none_on_malformed_json():
    config = _make_config()
    advisor = LLMAdvisor(config)

    with patch("trading_mcp.execution.llm_advisor.requests.post", return_value=_FakeResponse(_openrouter_payload("not json at all"))):
        decision = advisor.decide("BTC/USDT", 50000.0, "NEUTRAL", 3, [], [])

    assert decision.direction == "NONE"
    assert decision.confidence == 0.0


def test_decide_falls_back_to_none_on_invalid_direction():
    config = _make_config()
    advisor = LLMAdvisor(config)

    content = json.dumps({"direction": "SHORT", "confidence": 0.9, "reasoning": "robot ngaco"})
    with patch("trading_mcp.execution.llm_advisor.requests.post", return_value=_FakeResponse(_openrouter_payload(content))):
        decision = advisor.decide("BTC/USDT", 50000.0, "NEUTRAL", 3, [], [])

    assert decision.direction == "NONE"  # SHORT bukan arah valid untuk spot long-only


def test_decide_falls_back_to_none_on_network_error():
    config = _make_config()
    advisor = LLMAdvisor(config)

    with patch("trading_mcp.execution.llm_advisor.requests.post", side_effect=requests.ConnectionError("down")):
        decision = advisor.decide("BTC/USDT", 50000.0, "NEUTRAL", 3, [], [])

    assert decision.direction == "NONE"


def test_decide_falls_back_to_none_on_http_error_status():
    config = _make_config()
    advisor = LLMAdvisor(config)

    with patch("trading_mcp.execution.llm_advisor.requests.post", return_value=_FakeResponse({}, status=500)):
        decision = advisor.decide("BTC/USDT", 50000.0, "NEUTRAL", 3, [], [])

    assert decision.direction == "NONE"


def test_decide_clamps_confidence_to_0_1_range():
    config = _make_config()
    advisor = LLMAdvisor(config)

    content = json.dumps({"direction": "LONG_ENTRY", "confidence": 5.0, "reasoning": "overclaim"})
    with patch("trading_mcp.execution.llm_advisor.requests.post", return_value=_FakeResponse(_openrouter_payload(content))):
        decision = advisor.decide("BTC/USDT", 50000.0, "BULLISH", 7, [], [])

    assert decision.confidence == 1.0

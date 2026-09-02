import asyncio

import pytest

from app.providers.anthropic import AnthropicLLMProvider
from app.providers.base import LLMProviderError


def test_extracts_text_from_content_blocks() -> None:
    payload = {
        "content": [
            {"type": "text", "text": "Grounded answer"},
            {"type": "tool_use", "input": {}},
        ]
    }
    assert AnthropicLLMProvider._extract_text(payload) == "Grounded answer"


def test_missing_api_key_raises_provider_error(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    provider = AnthropicLLMProvider()
    with pytest.raises(LLMProviderError):
        asyncio.run(provider.complete("system", "prompt"))

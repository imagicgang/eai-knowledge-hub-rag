import asyncio

import pytest

from app.providers.base import LLMProviderError
from app.providers.gemini import GeminiLLMProvider


def test_extracts_text_from_candidate_parts() -> None:
    payload = {"candidates": [{"content": {"parts": [{"text": "Grounded answer"}]}}]}
    assert GeminiLLMProvider._extract_text(payload) == "Grounded answer"


def test_missing_api_key_raises_provider_error(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    provider = GeminiLLMProvider()
    with pytest.raises(LLMProviderError):
        asyncio.run(provider.complete("system", "prompt"))

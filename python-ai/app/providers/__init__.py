import os

from .base import LLMProvider, LLMProviderError
from .mock import MockLLMProvider
from .ollama import OllamaLLMProvider


def create_provider() -> LLMProvider:
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    if provider == "mock":
        return MockLLMProvider()
    if provider == "ollama":
        return OllamaLLMProvider()
    raise ValueError(f"Unsupported LLM provider: {provider}")


__all__ = ["LLMProvider", "LLMProviderError", "MockLLMProvider", "OllamaLLMProvider", "create_provider"]

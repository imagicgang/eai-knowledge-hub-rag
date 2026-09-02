import os

from .anthropic import AnthropicLLMProvider
from .base import LLMProvider, LLMProviderError
from .gemini import GeminiLLMProvider
from .mock import MockLLMProvider
from .ollama import OllamaLLMProvider
from .openai import OpenAILLMProvider


def create_provider(provider_name: str | None = None, model: str | None = None) -> LLMProvider:
    provider = (provider_name or os.getenv("LLM_PROVIDER", "ollama")).lower()
    if provider == "mock":
        return MockLLMProvider()
    if provider == "ollama":
        return OllamaLLMProvider(model=model)
    if provider == "openai":
        return OpenAILLMProvider(model=model)
    if provider in {"anthropic", "claude"}:
        return AnthropicLLMProvider(model=model)
    if provider in {"gemini", "google"}:
        return GeminiLLMProvider(model=model)
    raise ValueError(f"Unsupported LLM provider: {provider}")


__all__ = [
    "AnthropicLLMProvider",
    "GeminiLLMProvider",
    "LLMProvider",
    "LLMProviderError",
    "MockLLMProvider",
    "OllamaLLMProvider",
    "OpenAILLMProvider",
    "create_provider",
]

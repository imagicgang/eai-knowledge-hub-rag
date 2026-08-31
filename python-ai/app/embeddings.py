import hashlib
import math
import os
import re
from abc import ABC, abstractmethod

import httpx


class EmbeddingProviderError(RuntimeError):
    pass


class EmbeddingProvider(ABC):
    name: str
    model: str

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one dense vector for every input text."""


class HashEmbeddingProvider(EmbeddingProvider):
    """Deterministic fallback for tests and offline development."""

    name = "hash"
    model = "feature-hash-v1"

    def __init__(self, dimensions: int = 256) -> None:
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0] * self.dimensions
            for token in re.findall(r"[^\W_]{2,}", text.lower(), re.UNICODE):
                digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
                index = int.from_bytes(digest, "big") % self.dimensions
                vector[index] += 1.0
            magnitude = math.sqrt(sum(value * value for value in vector)) or 1.0
            vectors.append([value / magnitude for value in vector])
        return vectors


class OpenAIEmbeddingProvider(EmbeddingProvider):
    name = "openai"

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        self.model = model or os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.api_key:
            raise EmbeddingProviderError("OPENAI_API_KEY is required for semantic chunking")
        try:
            response = httpx.post(
                f"{self.base_url}/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "input": texts, "encoding_format": "float"},
                timeout=60,
            )
            response.raise_for_status()
            data = sorted(response.json()["data"], key=lambda item: item["index"])
            return [item["embedding"] for item in data]
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise EmbeddingProviderError(f"OpenAI embedding request failed: {error}") from error


class OllamaEmbeddingProvider(EmbeddingProvider):
    name = "ollama"

    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.getenv("OLLAMA_EMBEDDING_MODEL", "bge-m3")
        self.base_url = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")

    def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            response = httpx.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": texts},
                timeout=120,
            )
            response.raise_for_status()
            return response.json()["embeddings"]
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise EmbeddingProviderError(f"Ollama embedding request failed: {error}") from error


def create_embedding_provider() -> EmbeddingProvider:
    provider = os.getenv("EMBEDDING_PROVIDER", "hash").lower()
    if provider == "openai":
        return OpenAIEmbeddingProvider()
    if provider == "ollama":
        return OllamaEmbeddingProvider()
    if provider == "hash":
        return HashEmbeddingProvider()
    raise ValueError(f"Unsupported embedding provider: {provider}")

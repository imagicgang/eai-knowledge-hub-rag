import os

import httpx

from .base import LLMProvider, LLMProviderError


class OllamaLLMProvider(LLMProvider):
    """Lightweight local LLM adapter for an Ollama-compatible HTTP server."""

    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("OLLAMA_URL", "http://localhost:11434")).rstrip("/")
        self.model = model or os.getenv("OLLAMA_LLM_MODEL", "qwen3:1.7b")
        self.name = "ollama"

    async def complete(self, system_prompt: str, prompt: str, max_output_tokens: int = 600) -> str:
        payload = {
            "model": self.model,
            "stream": False,
            "think": False,
            "options": {"temperature": 0, "num_ctx": 8192, "num_predict": max_output_tokens},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
        }
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(f"{self.base_url}/api/chat", json=payload)
                response.raise_for_status()
                answer = response.json().get("message", {}).get("content", "").strip()
        except (httpx.HTTPError, ValueError) as error:
            raise LLMProviderError(f"Local Ollama model is unavailable: {error}") from error
        if not answer:
            raise LLMProviderError("Local Ollama model returned an empty response")
        return answer

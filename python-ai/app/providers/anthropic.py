import os

import httpx

from .base import LLMProvider, LLMProviderError


class AnthropicLLMProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, model: str | None = None) -> None:
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5")
        self.base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1").rstrip("/")

    async def complete(self, system_prompt: str, prompt: str, max_output_tokens: int = 600) -> str:
        if not self.api_key:
            raise LLMProviderError("ANTHROPIC_API_KEY is not configured")
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    f"{self.base_url}/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "system": system_prompt,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": max_output_tokens,
                        "temperature": 0,
                    },
                )
                response.raise_for_status()
                answer = self._extract_text(response.json())
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise LLMProviderError(f"Anthropic API request failed: {error}") from error
        if not answer:
            raise LLMProviderError("Anthropic API returned an empty response")
        return answer

    @staticmethod
    def _extract_text(payload: dict) -> str:
        texts = [item["text"] for item in payload["content"] if item.get("type") == "text"]
        return "\n".join(texts).strip()

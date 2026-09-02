import os

import httpx

from .base import LLMProvider, LLMProviderError


class GeminiLLMProvider(LLMProvider):
    name = "gemini"

    def __init__(self, model: str | None = None) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        self.base_url = os.getenv(
            "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"
        ).rstrip("/")

    async def complete(self, system_prompt: str, prompt: str, max_output_tokens: int = 600) -> str:
        if not self.api_key:
            raise LLMProviderError("GEMINI_API_KEY is not configured")
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    f"{self.base_url}/models/{self.model}:generateContent",
                    headers={"x-goog-api-key": self.api_key},
                    json={
                        "systemInstruction": {"parts": [{"text": system_prompt}]},
                        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "temperature": 0,
                            "maxOutputTokens": max_output_tokens,
                            "responseMimeType": "application/json",
                        },
                    },
                )
                response.raise_for_status()
                answer = self._extract_text(response.json())
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as error:
            raise LLMProviderError(f"Gemini API request failed: {error}") from error
        if not answer:
            raise LLMProviderError("Gemini API returned an empty response")
        return answer

    @staticmethod
    def _extract_text(payload: dict) -> str:
        parts = payload["candidates"][0]["content"]["parts"]
        return "\n".join(item["text"] for item in parts if item.get("text")).strip()

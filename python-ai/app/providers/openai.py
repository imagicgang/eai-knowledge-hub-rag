import asyncio
import os
import re

import httpx

from .base import LLMProvider, LLMProviderError


class OpenAILLMProvider(LLMProvider):
    """OpenAI Responses API adapter for source-grounded answer generation."""

    def __init__(self, model: str | None = None) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
        self.reasoning_effort = os.getenv("OPENAI_REASONING_EFFORT", "none")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.name = "openai"

    async def complete(self, system_prompt: str, prompt: str, max_output_tokens: int = 600) -> str:
        if not self.api_key:
            raise LLMProviderError("OPENAI_API_KEY is not configured in the project .env file")
        payload = {
            "model": self.model,
            "instructions": system_prompt,
            "input": prompt,
            "reasoning": {"effort": self.reasoning_effort},
            "max_output_tokens": max_output_tokens,
            "store": False,
        }
        max_attempts = max(1, int(os.getenv("OPENAI_MAX_RETRY_ATTEMPTS", "6")))
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response: httpx.Response | None = None
                for attempt in range(max_attempts):
                    response = await client.post(
                        f"{self.base_url}/responses",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        json=payload,
                    )
                    if response.status_code != 429 or attempt + 1 == max_attempts:
                        break
                    await asyncio.sleep(self._retry_delay(response, attempt))
                if response is None:
                    raise LLMProviderError("OpenAI API request was not attempted")
                response.raise_for_status()
                answer = self._extract_output_text(response.json())
        except httpx.HTTPStatusError as error:
            detail = self._error_message(error.response)
            raise LLMProviderError(f"OpenAI API request failed: {detail}") from error
        except (httpx.HTTPError, ValueError) as error:
            raise LLMProviderError(f"OpenAI API is unavailable: {error}") from error
        if not answer:
            raise LLMProviderError("OpenAI API returned an empty response")
        return answer

    @staticmethod
    def _bounded_context(context: list[str]) -> str:
        parts = []
        remaining_chars = 12_000
        for index, item in enumerate(context):
            snippet = item[: min(4000, remaining_chars)]
            if not snippet:
                break
            parts.append(f"[{index + 1}] {snippet}")
            remaining_chars -= len(snippet)
        return "\n\n".join(parts)

    @staticmethod
    def _extract_output_text(payload: dict) -> str:
        texts = []
        for item in payload.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text" and content.get("text"):
                    texts.append(content["text"])
        return "\n".join(texts).strip()

    @staticmethod
    def _error_message(response: httpx.Response) -> str:
        try:
            return response.json().get("error", {}).get("message") or f"HTTP {response.status_code}"
        except ValueError:
            return f"HTTP {response.status_code}"

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        candidates = [
            response.headers.get("retry-after"),
            response.headers.get("x-ratelimit-reset-tokens"),
        ]
        try:
            candidates.append(response.json().get("error", {}).get("message"))
        except ValueError:
            pass
        for value in candidates:
            if not value:
                continue
            direct = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*", value)
            if direct:
                return min(60.0, max(0.1, float(direct.group(1))))
            durations = re.findall(r"(\d+(?:\.\d+)?)\s*(ms|s|m)", value, re.IGNORECASE)
            if durations:
                seconds = sum(
                    float(amount) * {"ms": 0.001, "s": 1.0, "m": 60.0}[unit.lower()]
                    for amount, unit in durations
                )
                return min(60.0, max(0.1, seconds + 0.05))
        return min(30.0, 0.5 * (2**attempt))

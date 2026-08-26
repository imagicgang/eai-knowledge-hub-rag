import os

import httpx

from .base import LLMProvider, LLMProviderError
from .ollama import SYSTEM_PROMPT


class OpenAILLMProvider(LLMProvider):
    """OpenAI Responses API adapter for source-grounded answer generation."""

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.model = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
        self.reasoning_effort = os.getenv("OPENAI_REASONING_EFFORT", "none")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.name = "openai"

    async def generate(self, question: str, context: list[str]) -> str:
        if not self.api_key:
            raise LLMProviderError("OPENAI_API_KEY is not configured in the project .env file")
        if not context:
            return "ไม่พบข้อมูลที่เกี่ยวข้องใน Knowledge Source ที่ index ไว้ กรุณาระบุชื่อระบบ API ทีม หรือ dependency ให้ชัดเจนขึ้น"

        context_block = self._bounded_context(context)
        payload = {
            "model": self.model,
            "instructions": SYSTEM_PROMPT,
            "input": f"Question:\n{question}\n\nIndexed knowledge context:\n{context_block}",
            "reasoning": {"effort": self.reasoning_effort},
            "max_output_tokens": 600,
            "store": False,
        }
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    f"{self.base_url}/responses",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                )
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

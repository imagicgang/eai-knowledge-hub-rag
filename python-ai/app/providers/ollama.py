import os

import httpx

from .base import LLMProvider, LLMProviderError

SYSTEM_PROMPT = """You are the EAI Knowledge Hub assistant.
Answer only from the supplied enterprise knowledge context.
If the context is insufficient, clearly say that the indexed knowledge does not contain the answer.
Never invent systems, owners, dependencies, or technical details.
Answer in the same language as the user's question.
Be concise, and mention the relevant source facts in your explanation."""


class OllamaLLMProvider(LLMProvider):
    """Lightweight local LLM adapter for an Ollama-compatible HTTP server."""

    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("OLLAMA_URL", "http://localhost:11434")).rstrip("/")
        self.model = model or os.getenv("OLLAMA_LLM_MODEL", "qwen3:1.7b")
        self.name = "ollama"

    async def generate(self, question: str, context: list[str]) -> str:
        if not context:
            return "ไม่พบข้อมูลที่เกี่ยวข้องใน Knowledge Source ที่ index ไว้ กรุณาระบุชื่อระบบ API ทีม หรือ dependency ให้ชัดเจนขึ้น"

        context_parts = []
        remaining_chars = 3600
        for index, item in enumerate(context):
            snippet = item[: min(1200, remaining_chars)]
            if not snippet:
                break
            context_parts.append(f"[{index + 1}] {snippet}")
            remaining_chars -= len(snippet)
        context_block = "\n\n".join(context_parts)
        payload = {
            "model": self.model,
            "stream": False,
            "think": False,
            "options": {"temperature": 0, "num_ctx": 4096, "num_predict": 192},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Question:\n{question}\n\nIndexed knowledge context:\n{context_block}"},
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

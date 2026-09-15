from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

SYSTEM_PROMPT = """You are the EAI Knowledge Hub assistant.
Answer only from the supplied enterprise knowledge context.
If the context is insufficient, clearly say that the indexed knowledge does not contain the answer.
Never invent systems, owners, dependencies, or technical details.
Answer in the same language as the user's question.
Be concise, and mention the relevant source facts in your explanation."""

SUGGEST_FOLLOWUPS_SYSTEM_PROMPT = """You suggest natural follow-up questions for a knowledge-base assistant.
Given the user's question, the assistant's answer, and the indexed context, propose up to 3 short
follow-up questions the user might reasonably ask next. Output one question per line, no numbering,
no bullets, no extra commentary, in the same language as the question. If no sensible follow-up
exists, output nothing."""


class LLMProvider(ABC):
    """Vendor-neutral contract used by retrieval and agent orchestration."""

    @abstractmethod
    async def complete(self, system_prompt: str, prompt: str, max_output_tokens: int = 600) -> str:
        """Generate text for a vendor-neutral system/user prompt pair."""

    async def generate(self, question: str, context: list[str]) -> str:
        if not context:
            return "ไม่พบข้อมูลที่เกี่ยวข้องใน Knowledge Source ที่ index ไว้ กรุณาระบุชื่อระบบ API ทีม หรือ dependency ให้ชัดเจนขึ้น"
        context_block = "\n\n".join(f"[{index + 1}] {item}" for index, item in enumerate(context))
        return await self.complete(
            SYSTEM_PROMPT,
            f"Question:\n{question}\n\nIndexed knowledge context:\n{context_block}",
        )

    async def stream(self, question: str, context: list[str]) -> AsyncIterator[str]:
        yield await self.generate(question, context)

    async def suggest_followups(
        self, question: str, answer: str, context: list[str], limit: int = 3
    ) -> list[str]:
        if not context:
            return []
        context_block = "\n\n".join(f"[{index + 1}] {item}" for index, item in enumerate(context))
        raw = await self.complete(
            SUGGEST_FOLLOWUPS_SYSTEM_PROMPT,
            f"Question:\n{question}\n\nAnswer:\n{answer}\n\nIndexed knowledge context:\n{context_block}",
            max_output_tokens=200,
        )
        questions = [line.strip("-•* \t") for line in raw.splitlines() if line.strip()]
        return questions[:limit]


class LLMProviderError(RuntimeError):
    """Raised when the selected model provider cannot generate a response."""

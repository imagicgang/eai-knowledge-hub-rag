from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class LLMProvider(ABC):
    """Vendor-neutral contract used by retrieval and agent orchestration."""

    @abstractmethod
    async def generate(self, question: str, context: list[str]) -> str:
        raise NotImplementedError

    async def stream(self, question: str, context: list[str]) -> AsyncIterator[str]:
        yield await self.generate(question, context)

from .base import LLMProvider


class MockLLMProvider(LLMProvider):
    name = "mock"
    model = "template"

    async def complete(self, system_prompt: str, prompt: str, max_output_tokens: int = 600) -> str:
        return '{"break_after": []}'

    async def generate(self, question: str, context: list[str]) -> str:
        if not context:
            return "I couldn’t find that in the indexed enterprise knowledge. Try naming a system, API, or team."
        facts = "\n".join(f"• {item}" for item in context)
        return f"Based on the indexed knowledge:\n\n{facts}\n\nThis answer uses the local demo provider; connect a production LLM adapter when ready."

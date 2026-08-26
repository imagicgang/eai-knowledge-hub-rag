from app.providers.openai import OpenAILLMProvider


def test_extracts_text_from_responses_payload() -> None:
    payload = {
        "output": [
            {"type": "reasoning", "content": []},
            {"type": "message", "content": [{"type": "output_text", "text": "Grounded answer"}]},
        ]
    }
    assert OpenAILLMProvider._extract_output_text(payload) == "Grounded answer"


def test_context_is_bounded() -> None:
    context = OpenAILLMProvider._bounded_context(["a" * 10_000, "b" * 10_000])
    assert len(context) <= 12_020

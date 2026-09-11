import httpx

from app.embeddings import OpenAIEmbeddingProvider
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


def test_rate_limit_retry_delay_uses_reset_header() -> None:
    response = httpx.Response(429, headers={"x-ratelimit-reset-tokens": "146ms"})
    assert 0.19 < OpenAILLMProvider._retry_delay(response, 0) < 0.20


def test_embedding_batches_respect_byte_limit_and_keep_order() -> None:
    provider = OpenAIEmbeddingProvider(api_key="test")
    provider.max_batch_bytes = 5

    assert provider._batches(["aa", "bbb", "c", "dd"]) == [["aa", "bbb"], ["c", "dd"]]

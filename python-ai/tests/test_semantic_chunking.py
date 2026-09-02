import asyncio
import json

from app.embeddings import EmbeddingProvider
from app.ingestion import parse_file
from app.providers import LLMProvider
from app.semantic_chunking import (
    SemanticChunkingConfig,
    _parse_breakpoints,
    semantic_chunk,
    semantic_chunk_with_llm,
)


class FakeEmbeddingProvider(EmbeddingProvider):
    name = "fake"
    model = "test"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] if "payment" in text.lower() else [0.0, 1.0] for text in texts]


class FakeLLMProvider(LLMProvider):
    name = "fake"
    model = "test"

    async def complete(self, system_prompt: str, prompt: str, max_output_tokens: int = 600) -> str:
        return '{"break_after": [2]}'


def test_semantic_chunking_splits_when_topic_changes() -> None:
    chunks = semantic_chunk(
        ["Payment API", "Payment database", "Employee handbook"],
        FakeEmbeddingProvider(),
        SemanticChunkingConfig(
            similarity_threshold=0.8,
            min_chunk_chars=0,
            max_chunk_chars=1000,
            max_units_per_chunk=10,
        ),
    )
    assert chunks == ["Payment API\n\nPayment database", "Employee handbook"]


def test_python_functions_are_structural_units_before_semantic_merge() -> None:
    source = b"import os\n\ndef payment_total():\n    return 10\n\ndef employee_name():\n    return 'Ada'\n"
    chunks = parse_file("service.py", source, embedding_provider=FakeEmbeddingProvider())
    assert len(chunks) == 2
    assert any("def payment_total" in chunk for chunk in chunks)
    assert any("def employee_name" in chunk for chunk in chunks)


def test_drawio_entity_contains_its_relationship_context() -> None:
    xml = b'''<mxGraphModel><root>
      <mxCell id="a" value="Payment Service" vertex="1" />
      <mxCell id="b" value="Fraud Service" vertex="1" />
      <mxCell id="e" value="CALLS" edge="1" source="a" target="b" />
    </root></mxGraphModel>'''
    chunks = parse_file("architecture.drawio", xml, embedding_provider=FakeEmbeddingProvider())
    payment = next(chunk for chunk in chunks if "Diagram entity: Payment Service" in chunk)
    assert "Payment Service -> Fraud Service" in payment


def test_llm_chunking_uses_returned_topic_boundaries() -> None:
    chunks = asyncio.run(
        semantic_chunk_with_llm(
            ["Payment API", "Payment database", "Employee handbook"],
            FakeLLMProvider(),
            SemanticChunkingConfig(
                similarity_threshold=0.8,
                min_chunk_chars=0,
                max_chunk_chars=1000,
                max_units_per_chunk=10,
            ),
        )
    )
    assert chunks == ["Payment API\n\nPayment database", "Employee handbook"]


def test_breakpoints_recover_from_malformed_or_truncated_json() -> None:
    assert _parse_breakpoints('```json\n{"break_after": [2 5, 99]\n```', 10) == {2, 5}


class TopicShiftLLMProvider(LLMProvider):
    """Simulates a real classifier: breaks where the topic keyword changes."""

    name = "fake"
    model = "test"

    async def complete(self, system_prompt: str, prompt: str, max_output_tokens: int = 600) -> str:
        lines = [line for line in prompt.splitlines() if line.startswith("[")]
        topics = ["payment" if "payment" in line.lower() else "employee" for line in lines]
        breaks = [
            index + 1
            for index in range(len(topics) - 1)
            if topics[index] != topics[index + 1]
        ]
        return json.dumps({"break_after": breaks})


def test_llm_chunking_detects_topic_change_at_a_batch_seam(monkeypatch) -> None:
    """A topic change spanning exactly the batch boundary must still split.

    Regression test: batches used to be classified with zero visibility of
    neighboring batches, and the final position of every batch was excluded
    from the allowed break range, so a boundary could never land on the seam
    between two batches.
    """
    monkeypatch.setenv("CHUNKING_LLM_BATCH_UNITS", "2")
    monkeypatch.setenv("CHUNKING_LLM_OVERLAP_UNITS", "1")
    units = ["Payment API", "Payment database", "Employee handbook", "Employee vacation policy"]
    chunks = asyncio.run(
        semantic_chunk_with_llm(
            units,
            TopicShiftLLMProvider(),
            SemanticChunkingConfig(min_chunk_chars=0, max_chunk_chars=1000, max_units_per_chunk=10),
        )
    )
    assert chunks == [
        "Payment API\n\nPayment database",
        "Employee handbook\n\nEmployee vacation policy",
    ]

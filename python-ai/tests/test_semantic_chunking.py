from app.embeddings import EmbeddingProvider
from app.ingestion import parse_file
from app.semantic_chunking import SemanticChunkingConfig, semantic_chunk


class FakeEmbeddingProvider(EmbeddingProvider):
    name = "fake"
    model = "test"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] if "payment" in text.lower() else [0.0, 1.0] for text in texts]


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

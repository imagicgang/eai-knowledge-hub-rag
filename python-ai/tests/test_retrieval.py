import asyncio
import uuid

import httpx
import pytest

from app import retrieval
from app.embeddings import HashEmbeddingProvider
from app.retrieval import add_records, ensure_schema, retrieve, search


def _surreal_available() -> bool:
    try:
        httpx.get(f"{retrieval.SURREAL_URL}/health", timeout=1)
        return True
    except httpx.HTTPError:
        return False


pytestmark = pytest.mark.skipif(
    not _surreal_available(), reason="SurrealDB is not reachable at SURREAL_URL"
)


def test_keywords_for_lowercases_and_dedupes() -> None:
    assert retrieval.keywords_for("Payment Payment Service!") == ["payment", "service"]


def test_ingest_and_semantic_search_round_trip() -> None:
    asyncio.run(ensure_schema())
    provider = HashEmbeddingProvider()
    source = f"systems-{uuid.uuid4().hex}.csv"
    chunks = ["Inventory API is owned by the Supply Team."]
    embeddings = provider.embed(chunks)

    count = asyncio.run(add_records(source, chunks, embeddings, metadata="Source type: document."))
    assert count == 1

    vector = provider.embed(["Who owns Inventory API?"])[0]
    records = asyncio.run(retrieve("Who owns Inventory API?", vector, limit=3))
    assert records
    assert any(record.source == source and "Inventory API" in record.text for record in records)


def test_search_returns_graph_nodes_and_edges() -> None:
    asyncio.run(ensure_schema())
    provider = HashEmbeddingProvider()
    source = f"graph-{uuid.uuid4().hex}.csv"
    chunks = ["Order Service publishes order.created events to Kafka."]
    embeddings = provider.embed(chunks)
    asyncio.run(add_records(source, chunks, embeddings))

    vector = provider.embed(["What does Order Service publish?"])[0]
    result = asyncio.run(search("What does Order Service publish?", vector, limit=5))

    assert result["matches"]
    node_types = {node["type"] for node in result["nodes"]}
    assert "query" in node_types
    assert "chunk" in node_types
    assert any(edge["type"] == "match" for edge in result["edges"])


def test_add_records_requires_matching_embeddings() -> None:
    with pytest.raises(ValueError):
        asyncio.run(add_records("mismatch.csv", ["a", "b"], [[0.1]]))

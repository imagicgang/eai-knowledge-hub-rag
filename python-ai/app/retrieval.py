import base64
import json
import os
import re
from dataclasses import dataclass

import httpx

from .embeddings import EmbeddingProvider

# Docker Compose supplies the in-network URL explicitly. For local development,
# SurrealDB is published on host port 8010 so it does not conflict with FastAPI.
SURREAL_URL = os.getenv("SURREAL_URL", "http://localhost:8010").rstrip("/")
SURREAL_NS = os.getenv("SURREAL_NS", "eai")
SURREAL_DB = os.getenv("SURREAL_DB", "knowledge")
SURREAL_USER = os.getenv("SURREAL_USER", "root")
SURREAL_PASS = os.getenv("SURREAL_PASS", "root")

# New chunks are related to their most similar existing chunks so the index forms a
# navigable graph, not just a flat vector store. A per-insert neighbor cap keeps this
# O(new_chunks) instead of O(n^2) as the corpus grows.
GRAPH_NEIGHBOR_LIMIT = int(os.getenv("KNOWLEDGE_GRAPH_NEIGHBORS", "4"))
GRAPH_SIMILARITY_THRESHOLD = float(os.getenv("KNOWLEDGE_GRAPH_SIMILARITY", "0.75"))

DEMO_RECORDS: list[tuple[str, str]] = [
    ("Payment Service calls Fraud Service for risk checks.", "architecture/payment.drawio"),
    ("Payment Service writes transactions to Payment PostgreSQL.", "catalog/services.yaml"),
    ("Order API is owned by the Commerce Platform team.", "catalog/services.yaml"),
    ("Order Service publishes order.created events to Kafka.", "architecture/order.drawio"),
    ("Checkout Web calls Order API, which calls Payment Service.", "architecture/checkout.drawio"),
]


class SurrealError(RuntimeError):
    pass


@dataclass(frozen=True)
class KnowledgeRecord:
    id: str
    text: str
    source: str
    score: float = 0.0


def keywords_for(value: str) -> list[str]:
    return sorted({word.lower() for word in re.findall(r"[^\W_]{2,}", value, re.UNICODE)})


def _headers() -> dict[str, str]:
    token = base64.b64encode(f"{SURREAL_USER}:{SURREAL_PASS}".encode()).decode()
    return {
        "Accept": "application/json",
        "surreal-ns": SURREAL_NS,
        "surreal-db": SURREAL_DB,
        "Authorization": f"Basic {token}",
    }


def _string(value: str) -> str:
    """Render a Python string as a safely escaped SurrealQL string literal."""
    return json.dumps(value)


def _vector(values: list[float]) -> str:
    """Render an embedding as a SurrealQL array literal (values only, no injection risk)."""
    return "[" + ",".join(f"{float(value):.8f}" for value in values) + "]"


def _id_list(ids: list[str]) -> str:
    """Record ids returned by SurrealDB (e.g. chunk:abc123) are safe to splice back in raw."""
    return "[" + ",".join(ids) + "]"


async def _query(statement: str) -> list[object]:
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.post(
                f"{SURREAL_URL}/sql", headers=_headers(), content=statement.encode("utf-8")
            )
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise SurrealError(f"SurrealDB request failed: {error}") from error
    try:
        payload = response.json()
    except ValueError as error:
        raise SurrealError(f"SurrealDB returned an invalid response: {error}") from error
    results = []
    for item in payload:
        if item.get("status") != "OK":
            raise SurrealError(f"SurrealDB query failed: {item.get('result')}")
        results.append(item.get("result"))
    return results


async def ensure_schema() -> None:
    await _query(
        "DEFINE TABLE IF NOT EXISTS source SCHEMALESS;"
        "DEFINE TABLE IF NOT EXISTS chunk SCHEMALESS;"
        "DEFINE TABLE IF NOT EXISTS has_chunk TYPE RELATION IN source OUT chunk SCHEMALESS;"
        "DEFINE TABLE IF NOT EXISTS related_to TYPE RELATION IN chunk OUT chunk SCHEMALESS;"
    )


async def seed_demo_data(embedding_provider: EmbeddingProvider) -> None:
    """Populate a handful of demo chunks so the search UI has something to show pre-ingest."""
    existing = await _query("SELECT count() AS total FROM chunk GROUP ALL;")
    rows = existing[0] if existing else []
    if rows and rows[0].get("total"):
        return
    by_source: dict[str, list[str]] = {}
    for text, source in DEMO_RECORDS:
        by_source.setdefault(source, []).append(text)
    for source, texts in by_source.items():
        embeddings = embedding_provider.embed(texts)
        await add_records(source, texts, embeddings, metadata="Seed demo knowledge.")


async def add_records(
    source: str, chunks: list[str], embeddings: list[list[float]], metadata: str = ""
) -> int:
    if not chunks:
        return 0
    if len(chunks) != len(embeddings):
        raise ValueError("Each chunk requires exactly one embedding")

    source_thing = f'(type::thing("source", {_string(source)}))'
    await _query(
        f"DELETE chunk WHERE source = {_string(source)};"
        f"DELETE {source_thing};"
        f"CREATE {source_thing} SET name = {_string(source)}, metadata = {_string(metadata)}, "
        f"updated_at = time::now();"
    )

    chunk_ids: list[str] = []
    for text, embedding in zip(chunks, embeddings, strict=True):
        combined = f"{metadata} {text}".strip()
        result = await _query(
            f"CREATE chunk SET text = {_string(text)}, source = {_string(source)}, "
            f"metadata = {_string(metadata)}, keywords = {json.dumps(keywords_for(combined))}, "
            f"embedding = {_vector(embedding)}, created_at = time::now();"
        )
        chunk_id = result[0][0]["id"]
        chunk_ids.append(chunk_id)
        await _query(f"RELATE {source_thing}->has_chunk->{chunk_id} SET created_at = time::now();")

    for chunk_id, embedding in zip(chunk_ids, embeddings, strict=True):
        neighbors = await _query(
            f"SELECT id, vector::similarity::cosine(embedding, {_vector(embedding)}) AS score "
            f"FROM chunk WHERE id != {chunk_id} AND source != {_string(source)} "
            f"AND array::len(embedding) = {len(embedding)} "
            f"ORDER BY score DESC LIMIT {GRAPH_NEIGHBOR_LIMIT};"
        )
        for neighbor in neighbors[0] if neighbors else []:
            score = neighbor.get("score") or 0.0
            if score >= GRAPH_SIMILARITY_THRESHOLD:
                await _query(f"RELATE {chunk_id}->related_to->{neighbor['id']} SET score = {score:.4f};")

    return len(chunks)


async def search(question: str, vector: list[float], limit: int = 8) -> dict:
    """Semantic search over stored chunks plus the graph edges connecting the hits.

    Chunks are matched only against embeddings of the same dimension: switching
    EMBEDDING_PROVIDER over the life of a deployment can leave chunks of differing
    vector sizes in the same table, and comparing across sizes raises in SurrealDB.
    """
    rows = (
        await _query(
            f"SELECT id, text, source, vector::similarity::cosine(embedding, {_vector(vector)}) AS score "
            f"FROM chunk WHERE array::len(embedding) = {len(vector)} ORDER BY score DESC LIMIT {int(limit)};"
        )
    )[0] or []
    matches = [
        {"id": row["id"], "text": row["text"], "source": row["source"], "score": round(float(row["score"] or 0), 4)}
        for row in rows
    ]
    if not matches:
        return {"query": question, "matches": [], "nodes": [], "edges": []}

    ids = [match["id"] for match in matches]
    edge_rows = (
        await _query(f"SELECT in, out, score FROM related_to WHERE in IN {_id_list(ids)} OR out IN {_id_list(ids)};")
    )[0] or []

    source_names = sorted({match["source"] for match in matches})
    nodes = [{"id": "query", "label": question, "type": "query"}]
    nodes += [{"id": name, "label": name, "type": "source"} for name in source_names]
    nodes += [
        {
            "id": match["id"],
            "label": match["text"][:160],
            "type": "chunk",
            "score": match["score"],
            "source": match["source"],
        }
        for match in matches
    ]

    # has_chunk edges are derived from each match's own source field rather than
    # queried from the has_chunk table, since SurrealDB's record-id rendering for
    # source things (e.g. source:`services.csv`) would otherwise not line up with
    # the plain source-name node ids used above.
    edges = [{"source": "query", "target": match["id"], "type": "match", "weight": match["score"]} for match in matches]
    edges += [{"source": match["source"], "target": match["id"], "type": "has_chunk", "weight": 1.0} for match in matches]
    edges += [
        {"source": edge["in"], "target": edge["out"], "type": "related_to", "weight": round(float(edge["score"] or 0), 4)}
        for edge in edge_rows
    ]

    return {"query": question, "matches": matches, "nodes": nodes, "edges": edges}


async def retrieve(question: str, vector: list[float], limit: int = 3) -> list[KnowledgeRecord]:
    result = await search(question, vector, limit)
    return [
        KnowledgeRecord(id=match["id"], text=match["text"], source=match["source"], score=match["score"])
        for match in result["matches"]
    ]

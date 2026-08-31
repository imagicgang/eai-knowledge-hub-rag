import math
import os
from dataclasses import dataclass

from .embeddings import EmbeddingProvider


@dataclass(frozen=True)
class SemanticChunkingConfig:
    similarity_threshold: float = float(os.getenv("SEMANTIC_CHUNK_SIMILARITY", "0.55"))
    min_chunk_chars: int = int(os.getenv("SEMANTIC_CHUNK_MIN_CHARS", "300"))
    max_chunk_chars: int = int(os.getenv("SEMANTIC_CHUNK_MAX_CHARS", "2400"))
    max_units_per_chunk: int = int(os.getenv("SEMANTIC_CHUNK_MAX_UNITS", "12"))


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    denominator = math.sqrt(sum(value * value for value in left)) * math.sqrt(
        sum(value * value for value in right)
    )
    return sum(a * b for a, b in zip(left, right, strict=True)) / denominator if denominator else 0.0


def _split_oversized(unit: str, max_chars: int) -> list[str]:
    """Apply a safety bound without making fixed-size splitting the main strategy."""
    if len(unit) <= max_chars:
        return [unit]
    pieces: list[str] = []
    current: list[str] = []
    current_size = 0
    for line in unit.splitlines():
        if current and current_size + len(line) + 1 > max_chars:
            pieces.append("\n".join(current).strip())
            current, current_size = [], 0
        if len(line) > max_chars:
            if current:
                pieces.append("\n".join(current).strip())
                current, current_size = [], 0
            pieces.extend(line[index : index + max_chars] for index in range(0, len(line), max_chars))
        else:
            current.append(line)
            current_size += len(line) + 1
    if current:
        pieces.append("\n".join(current).strip())
    return [piece for piece in pieces if piece]


def semantic_chunk(
    units: list[str],
    embedding_provider: EmbeddingProvider,
    config: SemanticChunkingConfig | None = None,
) -> list[str]:
    """Merge adjacent structural units while their embedding meaning remains coherent."""
    settings = config or SemanticChunkingConfig()
    bounded = [
        piece
        for unit in units
        if unit.strip()
        for piece in _split_oversized(unit.strip(), settings.max_chunk_chars)
    ]
    if len(bounded) <= 1:
        return bounded

    vectors = embedding_provider.embed(bounded)
    if len(vectors) != len(bounded):
        raise ValueError("Embedding provider returned the wrong number of vectors")

    chunks: list[str] = []
    group = [bounded[0]]
    group_vectors = [vectors[0]]
    group_size = len(bounded[0])

    for unit, vector in zip(bounded[1:], vectors[1:], strict=True):
        centroid = [sum(values) / len(group_vectors) for values in zip(*group_vectors, strict=True)]
        fits = group_size + len(unit) + 2 <= settings.max_chunk_chars
        similarity = _cosine(centroid, vector)
        threshold = settings.similarity_threshold
        if group_size < settings.min_chunk_chars:
            threshold *= 0.8
        coherent = similarity >= threshold
        if fits and len(group) < settings.max_units_per_chunk and coherent:
            group.append(unit)
            group_vectors.append(vector)
            group_size += len(unit) + 2
        else:
            chunks.append("\n\n".join(group))
            group, group_vectors, group_size = [unit], [vector], len(unit)

    chunks.append("\n\n".join(group))
    return chunks

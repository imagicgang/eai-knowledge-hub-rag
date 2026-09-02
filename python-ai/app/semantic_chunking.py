import asyncio
import json
import math
import os
import re
from dataclasses import dataclass

from .embeddings import EmbeddingProvider
from .providers import LLMProvider


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


LLM_CHUNKING_PROMPT = """You identify semantic topic boundaries in ordered enterprise knowledge units.
Keep code declarations, spreadsheet records, diagram relationships, and closely related facts together.
Start a new chunk only when the primary subject, business entity, subsystem, or responsibility changes.
Prefer fewer, larger chunks: multiple consecutive units about the same entity belong in one chunk
even if each unit's wording, field, or attribute differs. Do not split on incidental wording changes.
Some leading or trailing units are shown only as surrounding context for continuity; still judge
whether a topic boundary falls immediately before or after them like any other unit.
Return JSON only in this exact shape: {"break_after": [2, 7]}.
Numbers are the one-based unit positions after which a chunk should end.
Do not include the final unit because it ends automatically."""


def _parse_breakpoints(response: str, unit_count: int) -> set[int]:
    match = re.search(r"\{.*\}", response, re.DOTALL)
    values: list[object] | None = None
    if match:
        try:
            payload = json.loads(match.group(0))
            candidate = payload.get("break_after", [])
            if isinstance(candidate, list):
                values = candidate
        except (json.JSONDecodeError, TypeError):
            pass

    if values is None:
        # Models occasionally omit a comma, add a code fence, or truncate the
        # closing JSON characters. Recover only integers inside break_after;
        # all other generated text remains untrusted and is ignored.
        array_match = re.search(
            r"[\"']?break_after[\"']?\s*:\s*\[([^\]]*)",
            response,
            re.IGNORECASE | re.DOTALL,
        )
        if not array_match:
            raise ValueError("Chunking LLM did not return a break_after array")
        values = [int(value) for value in re.findall(r"(?<![\w.])-?\d+(?![\w.])", array_match.group(1))]

    return {
        value
        for value in values
        if isinstance(value, int) and not isinstance(value, bool) and 0 < value < unit_count
    }


async def semantic_chunk_with_llm(
    units: list[str],
    provider: LLMProvider,
    config: SemanticChunkingConfig | None = None,
) -> list[str]:
    """Ask a configurable LLM for topic boundaries, using parallel bounded batches."""
    settings = config or SemanticChunkingConfig()
    bounded = [
        piece
        for unit in units
        if unit.strip()
        for piece in _split_oversized(unit.strip(), settings.max_chunk_chars)
    ]
    if len(bounded) <= 1:
        return bounded

    batch_size = max(2, int(os.getenv("CHUNKING_LLM_BATCH_UNITS", "25")))
    overlap = max(0, min(int(os.getenv("CHUNKING_LLM_OVERLAP_UNITS", "3")), batch_size // 2))
    concurrency = max(1, int(os.getenv("CHUNKING_LLM_CONCURRENCY", "1")))
    semaphore = asyncio.Semaphore(concurrency)

    async def classify(core_start: int, core_end: int) -> set[int]:
        """Classify one batch's boundaries using neighboring units as context only.

        Batches are classified independently, so without shared context every
        batch seam is invisible to the model on both sides. Widening the
        window with a read-only overlap lets it judge continuity across the
        seam, and restricting accepted positions to this batch's own
        [core_start, core_end] range avoids two overlapping batches
        double-deciding the same interior boundary.
        """
        window_start = max(0, core_start - overlap)
        window_end = min(len(bounded), core_end + overlap)
        window = bounded[window_start:window_end]
        lookback = core_start - window_start
        low, high = lookback, lookback + (core_end - core_start)
        numbered = "\n\n".join(
            f"[{index + 1}] {unit[:1200]}" for index, unit in enumerate(window)
        )
        async with semaphore:
            response = await provider.complete(
                LLM_CHUNKING_PROMPT,
                f"Ordered units:\n\n{numbered}",
                max_output_tokens=300,
            )
        try:
            raw = _parse_breakpoints(response, len(window))
        except (TypeError, ValueError):
            # A malformed model response must not make the source impossible to
            # ingest. Size/unit limits below remain a deterministic safe fallback.
            return set()
        return {window_start + value for value in raw if low <= value <= high}

    cores = [
        (core_start, min(core_start + batch_size, len(bounded)))
        for core_start in range(0, len(bounded), batch_size)
    ]
    results = await asyncio.gather(*(classify(core_start, core_end) for core_start, core_end in cores))
    breakpoints = set().union(*results)

    chunks: list[str] = []
    group: list[str] = []
    group_size = 0
    for index, unit in enumerate(bounded, start=1):
        fits = group_size + len(unit) + 2 <= settings.max_chunk_chars
        if group and (not fits or len(group) >= settings.max_units_per_chunk):
            chunks.append("\n\n".join(group))
            group, group_size = [], 0
        group.append(unit)
        group_size += len(unit) + 2
        if index in breakpoints:
            chunks.append("\n\n".join(group))
            group, group_size = [], 0
    if group:
        chunks.append("\n\n".join(group))
    return chunks

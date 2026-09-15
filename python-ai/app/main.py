import asyncio
import os
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from .embeddings import EmbeddingProviderError, create_embedding_provider
from .ingestion import MAX_CHUNKS, parse_file, parse_units
from .providers import LLMProviderError, create_provider
from .retrieval import (
    SurrealError,
    add_records,
    delete_source,
    ensure_schema,
    list_sources,
    retrieve,
    search,
    seed_demo_data,
)
from .semantic_chunking import semantic_chunk_with_llm

provider = create_provider()
embedding_provider = create_embedding_provider()
chunking_mode = os.getenv("SEMANTIC_CHUNKING_MODE", "embedding").lower()
if chunking_mode not in {"embedding", "llm"}:
    raise ValueError(f"Unsupported semantic chunking mode: {chunking_mode}")
chunking_provider = (
    create_provider(
        os.getenv("CHUNKING_LLM_PROVIDER", os.getenv("LLM_PROVIDER", "openai")),
        os.getenv("CHUNKING_LLM_MODEL") or None,
    )
    if chunking_mode == "llm"
    else None
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    for attempt in range(10):
        try:
            await ensure_schema()
            break
        except SurrealError:
            if attempt == 9:
                raise
            await asyncio.sleep(1)
    try:
        await seed_demo_data(embedding_provider)
    except (EmbeddingProviderError, SurrealError):
        pass  # Demo seeding is a convenience; a down embedding backend must not block startup.
    yield


app = FastAPI(title="EAI Knowledge AI", version="0.1.0", lifespan=lifespan)


class AnswerRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class AnswerResponse(BaseModel):
    answer: str
    sources: list[str]
    suggested_questions: list[str] = []


class IngestResponse(BaseModel):
    source: str
    chunks: int
    message: str


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=8, ge=1, le=50)


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "ai",
        "provider": getattr(provider, "name", "mock"),
        "model": getattr(provider, "model", "template"),
        "embedding_provider": embedding_provider.name,
        "embedding_model": embedding_provider.model,
        "chunking_mode": chunking_mode,
        "chunking_provider": getattr(chunking_provider, "name", embedding_provider.name),
        "chunking_model": getattr(chunking_provider, "model", embedding_provider.model),
        "storage": "surrealdb",
    }


@app.post("/v1/answer", response_model=AnswerResponse)
async def answer(request: AnswerRequest) -> AnswerResponse:
    try:
        vector = (await run_in_threadpool(embedding_provider.embed, [request.message]))[0]
        records = await retrieve(request.message, vector)
    except (EmbeddingProviderError, SurrealError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    try:
        response = await provider.generate(request.message, [record.text for record in records])
    except LLMProviderError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    try:
        suggested_questions = await provider.suggest_followups(
            request.message, response, [record.text for record in records]
        )
    except LLMProviderError:
        # Follow-up suggestions are a nice-to-have; never fail the answer because of them.
        suggested_questions = []
    return AnswerResponse(
        answer=response,
        sources=list(dict.fromkeys(record.source for record in records)),
        suggested_questions=suggested_questions,
    )


@app.post("/v1/knowledge/search")
async def knowledge_search(request: SearchRequest) -> dict:
    try:
        vector = (await run_in_threadpool(embedding_provider.embed, [request.query]))[0]
        return await search(request.query, vector, request.limit)
    except EmbeddingProviderError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except SurrealError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/v1/ingest", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest(
    file: Annotated[UploadFile, File()],
    source_type: Annotated[str, Form()] = "document",
    scope: Annotated[str, Form()] = "system",
    system: Annotated[str, Form()] = "",
    schema_name: Annotated[str, Form(alias="schema")] = "",
    version: Annotated[str, Form()] = "",
) -> IngestResponse:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="File is empty")
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File exceeds 20 MB")
    try:
        if chunking_provider:
            units = await run_in_threadpool(
                parse_units, file.filename or "upload", content, schema_name
            )
            chunks = (await semantic_chunk_with_llm(units, chunking_provider))[:MAX_CHUNKS]
        else:
            chunks = await run_in_threadpool(
                parse_file, file.filename or "upload", content, schema_name, embedding_provider
            )
    except EmbeddingProviderError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except LLMProviderError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except (ValueError, UnicodeDecodeError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    if not chunks:
        raise HTTPException(status_code=422, detail="No indexable knowledge was found in this file")
    metadata = f"Source type: {source_type}. Scope: {scope}. System: {system or 'unspecified'}. Version: {version or 'unspecified'}."
    try:
        embeddings = await run_in_threadpool(embedding_provider.embed, chunks)
        count = await add_records(file.filename or "upload", chunks, embeddings, metadata)
    except EmbeddingProviderError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except SurrealError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return IngestResponse(source=file.filename or "upload", chunks=count, message=f"Indexed {count} knowledge chunks")


@app.get("/v1/sources")
async def list_knowledge_sources() -> dict:
    try:
        return {"sources": await list_sources()}
    except SurrealError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.delete("/v1/sources/{name:path}")
async def delete_knowledge_source(name: str) -> dict:
    try:
        deleted = await delete_source(name)
    except SurrealError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Source not found")
    return {"source": name, "deleted_chunks": deleted}

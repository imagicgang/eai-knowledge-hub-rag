from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from .ingestion import parse_file
from .providers import LLMProviderError, create_provider
from .retrieval import add_records, retrieve

app = FastAPI(title="EAI Knowledge AI", version="0.1.0")
provider = create_provider()


class AnswerRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class AnswerResponse(BaseModel):
    answer: str
    sources: list[str]


class IngestResponse(BaseModel):
    source: str
    chunks: int
    message: str


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "ai",
        "provider": getattr(provider, "name", "mock"),
        "model": getattr(provider, "model", "template"),
    }


@app.post("/v1/answer", response_model=AnswerResponse)
async def answer(request: AnswerRequest) -> AnswerResponse:
    records = retrieve(request.message)
    try:
        response = await provider.generate(request.message, [record.text for record in records])
    except LLMProviderError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return AnswerResponse(answer=response, sources=list(dict.fromkeys(record.source for record in records)))


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
        chunks = parse_file(file.filename or "upload", content, schema_name)
    except (ValueError, UnicodeDecodeError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    if not chunks:
        raise HTTPException(status_code=422, detail="No indexable knowledge was found in this file")
    metadata = f"Source type: {source_type}. Scope: {scope}. System: {system or 'unspecified'}. Version: {version or 'unspecified'}."
    count = add_records(file.filename or "upload", chunks, metadata)
    return IngestResponse(source=file.filename or "upload", chunks=count, message=f"Indexed {count} knowledge chunks")

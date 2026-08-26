from fastapi import FastAPI
from pydantic import BaseModel, Field

from .providers import MockLLMProvider
from .retrieval import retrieve

app = FastAPI(title="EAI Knowledge AI", version="0.1.0")
provider = MockLLMProvider()


class AnswerRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class AnswerResponse(BaseModel):
    answer: str
    sources: list[str]


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "ai"}


@app.post("/v1/answer", response_model=AnswerResponse)
async def answer(request: AnswerRequest) -> AnswerResponse:
    records = retrieve(request.message)
    response = await provider.generate(request.message, [record.text for record in records])
    return AnswerResponse(answer=response, sources=list(dict.fromkeys(record.source for record in records)))

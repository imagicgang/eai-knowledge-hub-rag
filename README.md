# EAI Knowledge Hub RAG

An enterprise knowledge platform for asking questions across architecture, source code, documents, and structured data. The local stack includes a Next.js chat experience, Go application API, provider-agnostic Python retrieval service, and a lightweight local LLM through Ollama.

## Architecture

```text
Next.js frontend (:3000) → Go backend (:8080) → Python AI (:8000) → Ollama (:11434)
```

- `frontend/` — Next.js, TypeScript, and Tailwind chat interface.
- `backend/` — Go HTTP API, validation, upload handling, and AI service proxy.
- `python-ai/` — FastAPI ingestion, retrieval orchestration, and replaceable LLM providers.

The LLM and embedding providers are selected independently through `.env`. OpenAI with
`gpt-5.6-luna` and `text-embedding-3-small` is the default configuration. Ollama with
`qwen3:1.7b` and multilingual `bge-m3` remains available for fully local operation. A
deterministic hash embedder is used only for isolated tests and offline development.

## Quick start

Run all services with Docker:

```bash
docker compose up --build
```

Before starting, put your project API key in `.env` as `OPENAI_API_KEY`. The key stays server-side in the Python AI container and must never use a `NEXT_PUBLIC_` prefix.

To run fully locally, set both providers and start the optional profile (the profile pulls the
chat and embedding models):

```bash
export LLM_PROVIDER=ollama
export EMBEDDING_PROVIDER=ollama
docker compose --profile local-llm up -d --build
```

To keep OpenAI for chatbot answers while running semantic chunking locally, use:

```bash
export LLM_PROVIDER=openai
export EMBEDDING_PROVIDER=ollama
docker compose --profile local-embedding up -d --build
```

This profile pulls only `bge-m3`; it does not pull or run the local chat model.

To answer chatbot questions with Anthropic Claude instead of OpenAI, set `ANTHROPIC_API_KEY` in
`.env` and switch the answer provider (chunking, if LLM-assisted, is configured independently via
`CHUNKING_LLM_PROVIDER`):

```bash
export LLM_PROVIDER=anthropic
export ANTHROPIC_MODEL=claude-haiku-4-5
docker compose up -d --build
```

`google` is accepted as an alias for `gemini`, and `claude` for `anthropic`.

Semantic chunking also supports an LLM-assisted mode. The answer model and chunking model are
configured independently:

```env
LLM_PROVIDER=openai
OPENAI_MODEL=gpt-5.6-luna

SEMANTIC_CHUNKING_MODE=llm
CHUNKING_LLM_PROVIDER=openai
CHUNKING_LLM_MODEL=gpt-5.6-luna
```

`CHUNKING_LLM_PROVIDER` accepts `openai`, `anthropic`/`claude`, `gemini`, `ollama`, or `mock`.
Configure the corresponding `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `GEMINI_API_KEY`. For local
LLM chunking, use `ollama` and start the `local-llm` profile. LLM mode analyzes structural units in
bounded batches; embedding mode remains available for lower cost and predictable throughput.
`CHUNKING_LLM_BATCH_UNITS` defaults to `25` and `CHUNKING_LLM_CONCURRENCY` defaults to `1` to avoid
token-per-minute bursts. Batches are classified independently, so `CHUNKING_LLM_OVERLAP_UNITS`
(default `3`) shows each batch a few neighboring units from the adjacent batch as read-only context,
so the model can judge whether a topic boundary falls right at the batch seam instead of guessing
blind at every edge. OpenAI HTTP 429 responses are retried automatically using the provider's
rate-limit reset headers; `OPENAI_MAX_RETRY_ATTEMPTS` controls the retry limit.

Open [http://localhost:3000](http://localhost:3000), then try “What systems depend on Payment Service?”

To add your own knowledge, open **Knowledge sources** in the sidebar, choose the source type and
scope, then drop a file into the upload area. The MVP supports XLSX, CSV, YAML, JSON, Draw.io/XML,
PlantUML, Terraform, common source-code files, Markdown, and text. Parsers first create structural
units (rows, graph neighborhoods, functions/classes, or document sections), then embedding
similarity merges adjacent related units into semantic chunks. `SEMANTIC_CHUNK_SIMILARITY`,
`SEMANTIC_CHUNK_MIN_CHARS`, `SEMANTIC_CHUNK_MAX_CHARS`, and `SEMANTIC_CHUNK_MAX_UNITS` tune the
boundaries. Parsed knowledge is persisted in `data/knowledge/knowledge-index.json` on the host and
remains indexed after container rebuilds and `docker compose down`, including `down -v`. The index
is intentionally ignored by Git because it can contain enterprise data. Back up `data/knowledge/`
separately when the indexed knowledge must survive deletion of the project directory.

## Local development

```bash
# AI service
cd python-ai && python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/uvicorn app.main:app --reload

# Go API (separate terminal)
cd backend && go run ./cmd/server

# Frontend (separate terminal)
cd frontend && npm install && npm run dev
```

## Verification

```bash
cd backend && go test ./...
cd python-ai && .venv/bin/pytest
cd frontend && npm run lint && npm run build
```

## Next slice

Reuse the embedding provider for vector retrieval, then add normalized entities and graph
retrieval. Keep provider integrations behind adapters.

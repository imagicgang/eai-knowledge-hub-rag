# EAI Knowledge Hub RAG

An enterprise knowledge platform for asking questions across architecture, source code, documents, and structured data. This first vertical slice includes a polished chat experience, a Go application API, and a provider-agnostic Python retrieval service.

## Architecture

```text
Next.js web (:3000) → Go API (:8080) → Python AI (:8000)
```

- `web/` — Next.js, TypeScript, and Tailwind chat interface.
- `api/` — Go HTTP API, validation, CORS, and AI service proxy.
- `ai/` — FastAPI retrieval orchestration and replaceable LLM providers.

The included `MockLLMProvider` and small in-memory knowledge set make the full flow usable without credentials. They are seams for adding a vector database, graph store, and production model provider later.

## Quick start

Run all services with Docker:

```bash
docker compose up --build
```

Open [http://localhost:3000](http://localhost:3000), then try “What systems depend on Payment Service?”

## Local development

```bash
# AI service
cd ai && python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/uvicorn app.main:app --reload

# Go API (separate terminal)
cd api && go run ./cmd/server

# Frontend (separate terminal)
cd web && npm install && npm run dev
```

## Verification

```bash
cd api && go test ./...
cd ai && .venv/bin/pytest
cd web && npm run lint && npm run build
```

## Next slice

Add file upload and deterministic YAML/JSON ingestion, persist normalized entities, then replace the demo retriever with hybrid vector and graph retrieval. Keep provider SDKs behind adapters in `ai/app/providers/`.

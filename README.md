# EAI Knowledge Hub RAG

An enterprise knowledge platform for asking questions across architecture, source code, documents, and structured data. The local stack includes a Next.js chat experience, Go application API, provider-agnostic Python retrieval service, and a lightweight local LLM through Ollama.

## Architecture

```text
Next.js frontend (:3000) → Go backend (:8080) → Python AI (:8000) → Ollama (:11434)
```

- `frontend/` — Next.js, TypeScript, and Tailwind chat interface.
- `backend/` — Go HTTP API, validation, upload handling, and AI service proxy.
- `python-ai/` — FastAPI ingestion, retrieval orchestration, and replaceable LLM providers.

Docker uses Ollama with `qwen3:1.7b` by default. The model is approximately 1.4 GB and supports multilingual answers while keeping all prompts and knowledge local. A `MockLLMProvider` remains available for tests and offline development.

## Quick start

Run all services with Docker:

```bash
docker compose up --build
```

The first start downloads the local model and can take several minutes. Later starts reuse the `ollama-data` Docker volume.

Open [http://localhost:3000](http://localhost:3000), then try “What systems depend on Payment Service?”

To add your own knowledge, open **Knowledge sources** in the sidebar, choose the source type and scope, then drop a file into the upload area. The MVP supports XLSX, CSV, YAML, JSON, Draw.io/XML, Terraform, common source-code files, Markdown, and text. Parsed knowledge is persisted in the Docker volume `knowledge-data` and remains indexed after container restarts.

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

Replace lexical retrieval with multilingual embeddings and a vector store, then add normalized entities and graph retrieval. Keep provider integrations behind adapters in `python-ai/app/providers/`.

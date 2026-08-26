.PHONY: dev test lint build

dev:
	docker compose up --build

test:
	cd api && go test ./...
	cd ai && .venv/bin/pytest
	cd web && npm run lint

lint:
	cd api && gofmt -w .
	cd ai && .venv/bin/ruff check .
	cd web && npm run lint

build:
	cd api && go build ./cmd/server
	cd web && npm run build

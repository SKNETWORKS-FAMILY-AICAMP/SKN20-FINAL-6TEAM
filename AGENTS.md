# Bizi

> RAG-based integrated business consulting chatbot. 4 expert domains: 창업/지원, 재무/세무, 인사/노무, 법률.

## Commands
- Local dev: `docker compose -f docker-compose.local.yaml up --build` (ChromaDB + local model)
- Deploy test: `docker compose up --build` (production-like environment)
- Backend test: `.venv/bin/pytest backend/tests/ -v` (Mac/Linux) / `.venv\Scripts\pytest backend/tests/ -v` (Windows)
- Frontend test: `cd frontend && npm run test`
- RAG test: `.venv/bin/pytest rag/tests/ -v` (Mac/Linux) / `.venv\Scripts\pytest rag/tests/ -v` (Windows)
- E2E test: `cd frontend && npm run test:e2e`
- Lint: `ruff check . --fix` (Python) / `cd frontend && npx eslint --fix .` (TS)
- Typecheck: `cd frontend && npx tsc --noEmit`

## Architecture
- `backend/` — FastAPI + SQLAlchemy 2.0 (:8000)
- `frontend/` — React + TypeScript + Zustand (:5173)
- `rag/` — LangChain/LangGraph + ChromaDB (:8001)
- Nginx (:80, sole external entry): `/api/*` → backend, `/rag/*` → rag, `/*` → frontend
- DB: MySQL `bizi_db` — SSH Tunnel (:3306) → Bastion EC2 → AWS RDS
- Details: `rag/ARCHITECTURE.md`, `backend/database.sql`

## Workflow
- Record mistakes/corrections in `tasks/lessons.md`
- Write feature plans in `docs/plans/<feature>.md`

## Preferences
- Simplicity first: minimal changes, minimal code, don't touch surrounding code
- Reuse existing patterns: check existing code before introducing new patterns
- Per-service details: `backend/AGENTS.md`, `frontend/AGENTS.md`, `rag/AGENTS.md`

## Gotchas
- DB requires SSH Tunnel running first: `ssh -L 3306:... bastion` before any DB access
- Python `.venv` lives at project root only — no per-service venvs. Always use `.venv/bin/pytest`
- `EMBEDDING_PROVIDER` env var: `local` uses local model, `runpod` uses RunPod Serverless — wrong value silently changes embedding behavior
- `docker-compose.local.yaml` (ChromaDB + local model) vs `docker-compose.yaml` (production-like) — wrong file = wrong environment

## MUST NOT
- No hardcoding: API keys, DB connections, ports → use env vars / config files
- No magic numbers/strings: define as constants
- No duplicate code: extract to utility functions
- No secret exposure: no passwords/tokens in code/logs
- No raw SQL: use SQLAlchemy ORM

## Test Exclusion
`/test` directory is created for testing and is not part of the project

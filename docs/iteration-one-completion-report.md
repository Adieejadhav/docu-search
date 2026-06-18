# Docu Search - Iteration One Completion Report

Date: 2026-06-18

This document captures the current state of the project at the end of iteration one. It is intended to be the handoff reference before starting optimization, hardening, deployment packaging, or the next product iteration.

## Iteration Status

Iteration one is functionally complete for a local production-style RAG workflow:

- Parse supported document formats.
- Normalize parsed content into a consistent document/block schema.
- Create structure-aware parent-child chunks.
- Create local embeddings using `BAAI/bge-small-en-v1.5`.
- Store documents, chunks, embeddings, ingestion jobs, traces, chat sessions, and evaluation runs in PostgreSQL with pgvector.
- Retrieve relevant chunks with hybrid vector and lexical search.
- Generate grounded RAG answers using Ollama with `gpt-oss:120b-cloud`.
- Expose the workflow through CLI commands, FastAPI endpoints, and a React admin/chat frontend.
- Run evaluation cases and store evaluation history.
- Inspect documents, chunks, traces, metrics, ingestion jobs, and index state from the admin UI.

Latest verification:

- Backend tests: `62 passed, 1 warning` using `backend\.venv\Scripts\python.exe -m pytest`.
- Frontend production build: passed using `npm run build`.
- Frontend dev server script verified on `http://127.0.0.1:5174/`.

## High-Level Architecture

The project is organized into five main runtime layers:

1. Ingestion layer

   Responsible for accepting files, validating file types and sizes, parsing each file format, normalizing document blocks, and creating parent-child chunks.

2. Embedding and indexing layer

   Responsible for embedding child chunks and storing the indexed representation in PostgreSQL/pgvector. Parent chunks remain available for expanded context and citations.

3. Retrieval and RAG layer

   Responsible for hybrid retrieval, citation construction, context assembly, LLM answer generation, trace capture, and chat session persistence.

4. API layer

   Responsible for exposing public user-facing routes and protected admin routes through FastAPI.

5. Frontend layer

   Responsible for the user chat experience and the admin workbench used for ingestion, index inspection, evaluation, traces, metrics, and testing.

## Source Folder Structure

Generated folders such as `.git`, `.venv`, `node_modules`, `dist`, `__pycache__`, `.pytest_cache`, and package metadata are intentionally excluded from this tree. Runtime upload job folders are summarized under `storage/uploads`.

```text
docu-search/
|-- .env.example
|-- .gitignore
|-- docker-compose.yml
|-- Makefile
|-- README.md
|-- backend/
|   |-- pyproject.toml
|   |-- app/
|   |   |-- main.py
|   |   |-- api/
|   |   |   |-- __init__.py
|   |   |   |-- dependencies.py
|   |   |   |-- errors.py
|   |   |   |-- middleware.py
|   |   |   |-- router.py
|   |   |   |-- routes/
|   |   |   |   |-- __init__.py
|   |   |   |   |-- admin.py
|   |   |   |   |-- chat.py
|   |   |   |   |-- documents.py
|   |   |   |   |-- evaluation.py
|   |   |   |   |-- health.py
|   |   |   |   |-- ingestion.py
|   |   |   |   |-- search.py
|   |   |   |   |-- traces.py
|   |   |-- chat/
|   |   |   |-- __init__.py
|   |   |   |-- store.py
|   |   |-- cli/
|   |   |   |-- __init__.py
|   |   |   |-- ask_index.py
|   |   |   |-- chunk_documents.py
|   |   |   |-- clear_database.py
|   |   |   |-- index_chunks.py
|   |   |   |-- ingest_documents.py
|   |   |   |-- migrate_database.py
|   |   |   |-- parse_documents.py
|   |   |   |-- query_index.py
|   |   |   |-- run_ingestion_worker.py
|   |   |-- core/
|   |   |   |-- __init__.py
|   |   |   |-- constants.py
|   |   |   |-- env.py
|   |   |   |-- exceptions.py
|   |   |   |-- observability.py
|   |   |-- db/
|   |   |   |-- __init__.py
|   |   |   |-- health.py
|   |   |   |-- migrations.py
|   |   |-- embeddings/
|   |   |   |-- __init__.py
|   |   |   |-- base.py
|   |   |   |-- local_sentence_transformer.py
|   |   |   |-- pipeline.py
|   |   |-- evaluation/
|   |   |   |-- __init__.py
|   |   |   |-- dataset.py
|   |   |   |-- history.py
|   |   |   |-- runner.py
|   |   |   |-- schema.py
|   |   |-- indexing/
|   |   |   |-- __init__.py
|   |   |   |-- pgvector_index.py
|   |   |-- ingestion/
|   |   |   |-- __init__.py
|   |   |   |-- jobs.py
|   |   |   |-- orchestrator.py
|   |   |   |-- chunking/
|   |   |   |   |-- __init__.py
|   |   |   |   |-- chunk_schema.py
|   |   |   |   |-- chunker.py
|   |   |   |   |-- factory.py
|   |   |   |   |-- token_counter.py
|   |   |   |   |-- strategies/
|   |   |   |   |   |-- __init__.py
|   |   |   |   |   |-- base.py
|   |   |   |   |   |-- parent_child_chunker.py
|   |   |   |   |   |-- structure_grouper.py
|   |   |   |   |   |-- table_chunker.py
|   |   |   |-- normalizers/
|   |   |   |   |-- __init__.py
|   |   |   |   |-- block_schema.py
|   |   |   |   |-- document_normalizer.py
|   |   |   |   |-- metadata_normalizer.py
|   |   |   |   |-- pipeline.py
|   |   |   |   |-- source_location_normalizer.py
|   |   |   |   |-- table_normalizer.py
|   |   |   |   |-- text_normalizer.py
|   |   |   |-- parsers/
|   |   |   |   |-- __init__.py
|   |   |   |   |-- _tabular.py
|   |   |   |   |-- base.py
|   |   |   |   |-- csv_parser.py
|   |   |   |   |-- docx_parser.py
|   |   |   |   |-- factory.py
|   |   |   |   |-- json_parser.py
|   |   |   |   |-- markdown_parser.py
|   |   |   |   |-- pdf_parser.py
|   |   |   |   |-- pptx_parser.py
|   |   |   |   |-- text_parser.py
|   |   |   |   |-- xlsx_parser.py
|   |   |   |-- validators/
|   |   |   |   |-- __init__.py
|   |   |   |   |-- block_validator.py
|   |   |   |   |-- file_validator.py
|   |   |-- llm/
|   |   |   |-- __init__.py
|   |   |   |-- ollama_client.py
|   |   |-- rag/
|   |   |   |-- __init__.py
|   |   |   |-- answerer.py
|   |   |   |-- traces.py
|   |   |-- schemas/
|   |   |   |-- __init__.py
|   |   |   |-- api.py
|   |   |-- search/
|   |   |   |-- __init__.py
|   |   |   |-- retrieval/
|   |   |   |   |-- __init__.py
|   |   |   |   |-- retrieval_schema.py
|   |-- db/
|   |   |-- migrations/
|   |   |   |-- 001_pgvector_chunk_index.sql
|   |-- tests/
|   |   |-- api/
|   |   |   |-- test_app.py
|   |   |-- core/
|   |   |   |-- test_clear_database_cli.py
|   |   |   |-- test_env.py
|   |   |-- evaluation/
|   |   |   |-- test_evaluation_runner.py
|   |   |-- ingestion/
|   |   |   |-- test_additional_parsers.py
|   |   |   |-- test_block_validator.py
|   |   |   |-- test_chunk_documents_cli.py
|   |   |   |-- test_document_normalizer.py
|   |   |   |-- test_file_validator.py
|   |   |   |-- test_ingestion_orchestrator.py
|   |   |   |-- test_inspect_parser_output_cli.py
|   |   |   |-- test_markdown_parser.py
|   |   |   |-- test_parent_child_chunker.py
|   |   |   |-- test_parser_factory.py
|   |   |   |-- test_text_parser.py
|   |   |-- search/
|   |   |   |-- test_production_embedding_pgvector_and_rag.py
|-- docs/
|   |-- iteration-one-completion-report.md
|   |-- iteration-one-operations-runbook.md
|   |-- production-retrieval-setup.md
|   |-- parser-next-iteration/
|   |   |-- README.md
|-- evaluation/
|-- frontend/
|   |-- .env.example
|   |-- index.html
|   |-- package-lock.json
|   |-- package.json
|   |-- README.md
|   |-- tsconfig.app.json
|   |-- tsconfig.json
|   |-- vite.config.ts
|   |-- src/
|   |   |-- App.tsx
|   |   |-- main.tsx
|   |   |-- styles.css
|   |   |-- vite-env.d.ts
|   |   |-- app/
|   |   |   |-- AppDataContext.tsx
|   |   |   |-- AppShell.tsx
|   |   |   |-- navigation.ts
|   |   |-- components/
|   |   |   |-- AlertBanner.tsx
|   |   |   |-- DocumentList.tsx
|   |   |   |-- MarkdownAnswer.tsx
|   |   |   |-- MetricCard.tsx
|   |   |   |-- ResultItem.tsx
|   |   |   |-- ui/
|   |   |   |   |-- Badge.tsx
|   |   |   |   |-- Button.tsx
|   |   |   |   |-- ConfirmDialog.tsx
|   |   |   |   |-- EmptyState.tsx
|   |   |   |   |-- Panel.tsx
|   |   |   |   |-- Skeleton.tsx
|   |   |-- features/
|   |   |   |-- admin/
|   |   |   |   |-- AdminLayout.tsx
|   |   |   |   |-- AdminPrimitives.tsx
|   |   |   |   |-- AdminWorkbenchContext.tsx
|   |   |   |   |-- improvements.ts
|   |   |   |   |-- pages/
|   |   |   |   |   |-- AdminEvaluationPage.tsx
|   |   |   |   |   |-- AdminIndexPage.tsx
|   |   |   |   |   |-- AdminIngestionPage.tsx
|   |   |   |   |   |-- AdminOpsPage.tsx
|   |   |   |   |   |-- AdminOverviewPage.tsx
|   |   |   |   |   |-- AdminTestBenchPage.tsx
|   |   |   |   |   |-- AdminTracesPage.tsx
|   |   |   |-- chat/
|   |   |   |   |-- ChatPanel.tsx
|   |   |   |   |-- types.ts
|   |   |-- lib/
|   |   |   |-- format.ts
|   |   |-- services/
|   |   |   |-- api.ts
|   |   |   |-- types.ts
|-- scripts/
|-- storage/
|   |-- 09_aquila_nested_corpus.parsed.json
|   |-- rag_robust_format_test_corpus.chunks.json
|   |-- rag_robust_format_test_corpus.normalized.json
|   |-- rag_robust_format_test_corpus.retrieval.json
|   |-- uploads/
|   |   |-- <ingestion-job-id>/
|   |   |   |-- uploaded source files
```

## Backend Folders

### `backend/app/main.py`

FastAPI application factory. It configures:

- App title and version.
- Request context middleware.
- In-memory rate limiting middleware.
- CORS for local frontend ports.
- Central `AppError` handling.
- API router registration.

### `backend/app/api`

Contains all API wiring:

- `router.py`: registers public and admin routes.
- `dependencies.py`: admin-token dependency.
- `errors.py`: maps internal app errors to API responses.
- `middleware.py`: request IDs, request timing, metrics, and rate limiting.
- `routes/`: route modules.

Public routes:

- `GET /health`
- `GET /documents`
- `POST /search`
- `POST /ask`
- `GET /chat/sessions`
- `POST /chat/sessions`
- `GET /chat/sessions/{session_id}`
- `DELETE /chat/sessions/{session_id}`
- `POST /chat/ask`
- `POST /chat/ask/stream`

Protected admin routes:

- `POST /admin/index/clear`
- `GET /admin/metrics`
- `GET /admin/auth/status`
- `GET /admin/documents/{document_id}/chunks`
- `DELETE /admin/documents/{document_id}`
- `POST /admin/documents/{document_id}/reindex`
- `POST /admin/ingestion/jobs`
- `GET /admin/ingestion/jobs`
- `GET /admin/ingestion/jobs/{job_id}`
- `GET /admin/evaluation/cases`
- `POST /admin/evaluation/run`
- `GET /admin/evaluation/runs`
- `GET /admin/evaluation/runs/{run_id}`
- `GET /admin/traces`
- `GET /admin/traces/{trace_id}`
- `DELETE /admin/traces`

### `backend/app/core`

Shared infrastructure:

- `env.py`: loads `.env` from repo/backend locations and reads environment settings.
- `exceptions.py`: application error types.
- `constants.py`: central constants.
- `observability.py`: request/metric helpers.

### `backend/app/db`

Database health and migration utilities:

- `health.py`: PostgreSQL health checks.
- `migrations.py`: local SQL migration runner.

### `backend/app/ingestion`

The ingestion domain:

- `orchestrator.py`: full parse -> normalize -> chunk -> embed -> index workflow.
- `jobs.py`: ingestion job persistence and execution service.
- `parsers/`: format-specific parsers for text, markdown, PDF, DOCX, PPTX, XLSX, CSV, and JSON.
- `normalizers/`: document/block schema cleanup, metadata cleanup, table cleanup, source-location cleanup, text cleanup.
- `validators/`: file and block validation.
- `chunking/`: parent-child chunk schema and strategy implementation.

Supported file types in iteration one:

- `.txt`
- `.md`
- `.markdown`
- `.pdf`
- `.docx`
- `.pptx`
- `.xlsx`
- `.csv`
- `.json`

### `backend/app/ingestion/chunking`

Structure-aware parent-child chunking:

- Parent chunks preserve larger logical sections.
- Child chunks are smaller retrieval units and are embedded.
- Child chunks keep a `parent_chunk_id` so retrieval can return precise matches while answers still have richer parent context.
- Tables and code-like blocks are treated carefully so they are not blindly split into useless fragments.

### `backend/app/embeddings`

Embedding provider layer:

- `base.py`: provider contract and vector validation.
- `local_sentence_transformer.py`: local `sentence-transformers` provider.
- `pipeline.py`: applies embeddings to child chunks.

Current model:

- `BAAI/bge-small-en-v1.5`
- 384 dimensions
- CPU by default

### `backend/app/indexing`

PostgreSQL/pgvector index implementation:

- Stores documents, parent chunks, child chunks, and child embeddings.
- Uses HNSW vector index for cosine search.
- Uses PostgreSQL full-text search indexes for lexical search.
- Supports hybrid vector plus lexical retrieval.
- Supports document listing, chunk inspection, delete, clear, and re-index workflows.

### `backend/app/rag`

RAG answer logic:

- `answerer.py`: retrieves context, calls the LLM, creates citations.
- `traces.py`: stores retrieval and answer traces for inspection.

### `backend/app/llm`

LLM integration:

- `ollama_client.py`: non-streaming and streaming Ollama chat client.

Current configured model:

- `gpt-oss:120b-cloud`

### `backend/app/chat`

Chat persistence:

- Chat sessions.
- User and assistant messages.
- Source metadata.
- Trace IDs.
- Latency metadata.

### `backend/app/evaluation`

Evaluation layer:

- `dataset.py`: built-in evaluation cases.
- `runner.py`: executes retrieval and optional answer checks.
- `schema.py`: typed evaluation request and response models.
- `history.py`: persists evaluation runs.

Evaluation checks include:

- Expected source hit.
- Required answer/context terms.
- Latency measurements.
- Pass/fail summaries.

### `backend/app/cli`

Operational command-line tools:

- `ingest_documents.py`: full ingestion pipeline.
- `parse_documents.py`: parse only.
- `chunk_documents.py`: chunk normalized documents.
- `index_chunks.py`: index existing chunks.
- `ask_index.py`: ask RAG question against index.
- `query_index.py`: retrieve without answer generation.
- `clear_database.py`: clear indexed/runtime database data.
- `migrate_database.py`: apply SQL migrations.
- `run_ingestion_worker.py`: run queued ingestion jobs in worker mode.

### `backend/db/migrations`

SQL migration files. Iteration one has:

- `001_pgvector_chunk_index.sql`

It creates:

- `vector` extension
- `index_metadata`
- `documents`
- `parent_chunks`
- `child_chunks`
- `child_embeddings`
- `ingestion_jobs`
- `rag_traces`
- `chat_sessions`
- `chat_messages`
- `evaluation_runs`

## Frontend Folders

### `frontend/src/app`

Application shell and routing:

- `AppShell.tsx`: main layout frame.
- `AppDataContext.tsx`: shared app data refresh/context.
- `navigation.ts`: navigation model.

### `frontend/src/components`

Reusable UI components:

- Alerts
- Metrics
- Markdown answer rendering
- Document list
- Result item rendering
- Shared UI primitives under `components/ui`

### `frontend/src/features/chat`

User-facing chat experience:

- Chat session list.
- Chat creation/deletion.
- Streaming answer flow.
- Markdown answer display.
- Citations and source display.

### `frontend/src/features/admin`

Admin workbench:

- `AdminLayout.tsx`: admin layout.
- `AdminPrimitives.tsx`: admin UI primitives.
- `AdminWorkbenchContext.tsx`: shared admin data.
- `improvements.ts`: improvement-area content.
- `pages/`: admin pages.

Current admin pages:

- Overview
- Ingestion
- Index
- Evaluation
- Traces
- Operations
- Test bench

### `frontend/src/services`

Typed API client:

- Central request handling.
- Admin token header support.
- Frontend models matching backend response shapes.

### `frontend/src/lib`

Formatting helpers:

- Numbers
- Durations
- Dates
- Percentages

## Database Design

The database is PostgreSQL with pgvector.

Important tables:

- `documents`: one row per ingested source document.
- `parent_chunks`: larger structure-aware chunks.
- `child_chunks`: smaller retrieval chunks.
- `child_embeddings`: vector embeddings for child chunks.
- `ingestion_jobs`: admin ingestion job state, timings, events, and errors.
- `rag_traces`: query, answer, context, citations, timings.
- `chat_sessions`: chat conversation records.
- `chat_messages`: persisted chat messages.
- `evaluation_runs`: stored evaluation history.

The embedding vector is stored directly in PostgreSQL using:

```sql
embedding vector(384)
```

The vector index is:

```sql
USING hnsw (embedding vector_cosine_ops)
```

Full-text indexes exist on parent and child chunk text for lexical retrieval.

## Current Environment Variables

Backend `.env.example` defines:

```text
DATABASE_URL=postgresql://docusearch:docusearch@localhost:55432/docusearch
EMBEDDING_PROVIDER=local
LOCAL_EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
LOCAL_EMBEDDING_DIMENSIONS=384
LOCAL_EMBEDDING_DEVICE=cpu
LOCAL_EMBEDDING_BATCH_SIZE=64
DOCU_SEARCH_UPLOAD_ROOT=../storage/uploads
INGESTION_RUN_MODE=background
HYBRID_VECTOR_WEIGHT=0.62
HYBRID_LEXICAL_WEIGHT=0.30
HYBRID_PHRASE_WEIGHT=0.08
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=gpt-oss:120b-cloud
OLLAMA_TEMPERATURE=0
API_CORS_ORIGINS=http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5174,http://localhost:5174
API_RATE_LIMIT_PER_MINUTE=120
MAX_UPLOAD_FILES=100
MAX_UPLOAD_FILE_SIZE_BYTES=26214400
LOG_LEVEL=INFO
ADMIN_API_TOKEN=
```

Frontend `.env.example` defines:

```text
VITE_API_BASE_URL=/api
VITE_ADMIN_TOKEN=
```

Do not commit real `.env` files.

## Main Commands

Start PostgreSQL/pgvector:

```powershell
docker compose up -d
```

Apply DB migration:

```powershell
cd C:\docu-search\backend
.\.venv\Scripts\python.exe -m app.cli.migrate_database
```

Start backend:

```powershell
cd C:\docu-search\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Start frontend:

```powershell
cd C:\docu-search\frontend
npm run dev
```

Run full ingestion from a local folder:

```powershell
cd C:\docu-search\backend
.\.venv\Scripts\python.exe -m app.cli.ingest_documents "C:\Users\ADINATH\Downloads\rag_robust_format_test_corpus\rag_robust_format_test_corpus" --recursive --normalized-output-json "..\storage\rag_robust_format_test_corpus.normalized.json" --chunks-output-json "..\storage\rag_robust_format_test_corpus.chunks.json"
```

Ask the index:

```powershell
cd C:\docu-search\backend
.\.venv\Scripts\python.exe -m app.cli.ask_index "Which policy mentions the 14-day satellite-mode exception?" --top-k 5 --show-context
```

Clear database runtime/index data:

```powershell
cd C:\docu-search\backend
.\.venv\Scripts\python.exe -m app.cli.clear_database
```

Run tests:

```powershell
cd C:\docu-search\backend
.\.venv\Scripts\python.exe -m pytest
```

Build frontend:

```powershell
cd C:\docu-search\frontend
npm run build
```

Stop local backend/frontend ports:

```powershell
foreach ($port in 5174,8001) {
  Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue |
    Where-Object State -eq Listen |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
}
```

## Known Current Runtime Baseline

The robust test corpus run produced:

- Input documents: 10
- Parent chunks: 211
- Child chunks: 282
- Indexed child chunks: 282
- Embedding model: `local-sentence-transformers-BAAI/bge-small-en-v1.5-384d`
- Embedding dimensions: 384

Sample question tested:

```text
Which policy mentions the 14-day satellite-mode exception?
```

Expected answer:

```text
P-004, Password rotation exception.
```

The system retrieved the relevant policy context and generated the correct answer with citations.

## What Is Complete

### Ingestion

- Multi-format document parsing.
- File validation.
- Metadata preservation.
- Source references.
- Normalized document output.
- Parent-child chunk output.
- CLI ingestion.
- API/admin ingestion.
- Upload support.
- Background ingestion mode.
- Worker ingestion mode.
- Ingestion job persistence.
- Live progress events and timings.

### Chunking

- Structure-aware parent-child chunking.
- Parent context preservation.
- Child chunk retrieval units.
- Table-aware handling.
- Source block tracking.
- Source reference tracking.
- Parent path preservation.

### Embeddings

- Local sentence-transformers provider.
- BGE small English model support.
- Batch embedding.
- Embedding validation.
- Environment-configurable model/device/batch size.

### Indexing

- PostgreSQL/pgvector storage.
- HNSW vector index.
- Full-text indexes.
- Hybrid retrieval.
- Index clear.
- Document delete.
- Document re-index.
- Document chunk inspection.

### RAG

- Retrieval.
- Context formatting.
- Ollama answer generation.
- Streaming and non-streaming answer paths.
- Citations.
- Trace persistence.
- Latency capture.

### Chat

- Chat sessions.
- Chat messages.
- Streaming chat endpoint.
- Source metadata on assistant responses.
- Trace linking.

### Evaluation

- Built-in evaluation dataset.
- Evaluation run endpoint.
- Evaluation history persistence.
- Source hit checks.
- Required term checks.
- Latency metrics.
- Admin evaluation UI.

### Frontend

- Modern React/Vite app.
- User chat area.
- Admin workbench.
- Ingestion upload and job monitoring.
- Index document/chunk management.
- Evaluation page.
- Trace inspection.
- Operations/metrics page.
- Test bench.

### Operations

- Docker Compose PostgreSQL/pgvector.
- SQL migrations.
- `.env.example` files.
- Optional admin API token.
- CORS configuration.
- Rate limiting.
- Request metrics.
- Health checks.
- CLI tools for local production-style workflows.

## What Is Not Yet Complete

These are not blockers for iteration one, but they are the logical next work items:

- Authentication should become real user/session auth instead of optional static admin token.
- In-memory rate limiting should move to Redis or database-backed rate limiting for multi-process deployment.
- Ingestion worker should become a proper service/process with retry policy and observability.
- Evaluation should support uploaded custom datasets.
- RAG quality metrics should include precision/recall style retrieval metrics against larger gold datasets.
- Frontend should add stronger loading, retry, and partial-failure states in more pages.
- API should get OpenAPI examples and stricter request validation descriptions.
- Deployment packaging should be added for backend, frontend, worker, PostgreSQL, and Ollama connectivity.
- `.env` handling should be audited before any public repository push.

## First Iteration Conclusion

The first iteration can be marked complete as a local production-grade baseline. The system is not just a parser or a toy retrieval demo now. It has a complete flow from document ingestion to grounded answers, with pgvector persistence, admin visibility, evaluation, traces, chat persistence, and frontend workflows.

The next phase should focus on hardening, quality measurement, deployment readiness, and deeper UI/UX polish rather than adding more core RAG plumbing.

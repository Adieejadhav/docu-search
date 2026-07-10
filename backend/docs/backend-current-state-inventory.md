# Backend Current-State Inventory and Baseline

Date: 2026-07-10

Scope: phase 1 only. This document records current backend behavior before any
structural refactor. No runtime behavior, route, schema, migration, or import
changes were made while preparing this inventory.

## Baseline Validation

Backend test commands tried:

```powershell
cd C:\docu-search\backend
python -m pytest
```

Result: failed during collection with the global Python because `fastapi` was
not installed there.

```powershell
cd C:\docu-search\backend
.\.venv\Scripts\python.exe -m pytest
```

Result: collected 63 tests, 33 passed, 30 setup errors. The errors were caused
by `PermissionError` reading the default Windows pytest temp directory
`C:\Users\ADINATH\AppData\Local\Temp\pytest-of-ADINATH`.

Usable baseline command:

```powershell
cd C:\docu-search\backend
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider --basetemp .tmp\pytest-baseline
```

Result:

```text
63 passed, 1 warning in 1.81s
```

Warning: `StarletteDeprecationWarning` from `fastapi.testclient` importing the
deprecated `httpx` based Starlette test client.

Backend startup check:

```powershell
cd C:\docu-search\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8017
```

Result: temporary process started and `GET http://127.0.0.1:8017/` returned:

```json
{"service":"docu-search-backend","status":"ok"}
```

OpenAPI baseline:

```text
title: Docu Search API
version: 0.1.0
path count: 22
component schema count: 43
sha256: 6b923fff81cb7d12633f471957558f1d10c24407387c4593bcfe497738440284
```

Database health baseline:

```text
ok: true
pgvector_available: true
pgvector_version: 0.8.2
tables present: documents, parent_chunks, child_chunks, child_embeddings
```

Docker baseline:

```text
docker compose ps
```

Result: blocked by local Docker permissions. The Docker client could not read
`C:\Users\ADINATH\.docker\config.json` and could not access the Docker engine
pipe.

## Registered Routes

Routes are from the current OpenAPI schema. The frontend accesses them through
`/api` in Vite, which rewrites `/api/*` to backend root paths.

```text
GET    /
GET    /health
GET    /documents
GET    /documents/{document_id}/source
POST   /search
POST   /ask
GET    /chat/sessions
POST   /chat/sessions
GET    /chat/sessions/{session_id}
DELETE /chat/sessions/{session_id}
POST   /chat/ask
POST   /chat/ask/stream
POST   /admin/index/clear
GET    /admin/overview
GET    /admin/metrics
GET    /admin/auth/status
GET    /admin/documents/{document_id}/chunks
DELETE /admin/documents/{document_id}
POST   /admin/documents/{document_id}/reindex
POST   /admin/ingestion/jobs
GET    /admin/ingestion/jobs
GET    /admin/ingestion/jobs/{job_id}
POST   /admin/pipeline/test
GET    /admin/traces
DELETE /admin/traces
GET    /admin/traces/{trace_id}
```

Important route behavior:

- Admin routes depend on `require_admin`; they are open unless
  `ADMIN_API_TOKEN` is configured.
- `POST /chat/ask/stream` returns `text/event-stream` and sets
  `Cache-Control: no-cache` and `X-Accel-Buffering: no`.
- Removed evaluation endpoints currently return 404 according to API tests.

## Request And Response Schemas

Schema modules:

```text
backend/app/schemas/common.py
backend/app/schemas/health.py
backend/app/schemas/documents.py
backend/app/schemas/search.py
backend/app/schemas/chat.py
backend/app/schemas/ingestion.py
backend/app/schemas/pipeline.py
backend/app/schemas/traces.py
backend/app/schemas/admin.py
```

OpenAPI component schemas:

```text
AdminClearIndexRequest
AdminClearIndexResponse
AdminOverviewHealth
AdminOverviewIndexStats
AdminOverviewIngestionJobs
AdminOverviewQueryCounts
AdminOverviewRecentJob
AdminOverviewRecentTrace
AdminOverviewResponse
AdminOverviewRisk
AskRequest
AskResponse
ChatAskRequest
ChatAskResponse
ChatMessageResponse
ChatSessionCreateRequest
ChatSessionDeleteResponse
ChatSessionDetail
ChatSessionListResponse
ChatSessionSummary
DocumentChunkListResponse
DocumentChunkSummary
DocumentDeleteResponse
DocumentListResponse
DocumentSummary
HealthResponse
HealthServiceStatus
IngestionJobCreateResponse
IngestionJobEventResponse
IngestionJobListResponse
IngestionJobResponse
PipelineNodeTestResponse
RagTraceDeleteResponse
RagTraceDetail
RagTraceListResponse
RagTraceSummary
RetrievedChunkResponse
SearchRequest
SearchResponse
```

Multipart body schemas also exist for:

```text
Body_create_ingestion_job_admin_ingestion_jobs_post
Body_test_pipeline_node_admin_pipeline_test_post
```

Key validation:

- `SearchRequest.query` is required, trimmed through `clean_required_text`, and
  must be non-empty.
- `SearchRequest.top_k` defaults to 5 and is constrained to 1 through 50.
- Document and ingestion list endpoints constrain `limit` and `offset` at the
  route layer.
- `ChatSessionCreateRequest.title` is optional and capped at 160 characters.
- Errors use `ApiErrorResponse` with `code`, `message`, and `details`.

## Current Services And Workflow Coordinators

Current service-like classes:

```text
SearchService                    backend/app/search/service.py
ChatService                      backend/app/chat/service.py
AdminOverviewService             backend/app/admin/overview.py
IngestionJobService              backend/app/ingestion/jobs.py
PipelineNodeTester               backend/app/ingestion/pipeline_testing.py
IngestionOrchestrator            backend/app/ingestion/orchestrator.py
RagAnswerer                      backend/app/rag/answerer.py
```

Current repository-like persistence classes:

```text
PgVectorChunkIndex               backend/app/indexing/pgvector_index.py
ChatStore                        backend/app/chat/store.py
IngestionJobStore                backend/app/ingestion/jobs.py
RagTraceStore                    backend/app/rag/traces.py
SqlMigrationRunner               backend/app/migrations.py
```

Current integration classes:

```text
LocalSentenceTransformerEmbeddingProvider
OllamaChatClient
connect_postgres
```

## Database Access Code

Raw SQL currently appears in:

```text
backend/app/indexing/pgvector_index.py
backend/app/chat/store.py
backend/app/ingestion/jobs.py
backend/app/rag/traces.py
backend/app/admin/overview.py
backend/app/db/health.py
backend/app/migrations.py
backend/app/cli/clear_database.py
```

Connection behavior:

- `connect_postgres()` opens a new `psycopg.connect(...)` connection per call.
- There is no shared connection pool yet.
- `DATABASE_CONNECT_TIMEOUT_SECONDS` defaults to 2 seconds.
- Most stores call `initialize()` before operations and create their own tables
  with `CREATE TABLE IF NOT EXISTS`.

## Current RAG Flow

One-shot answer flow:

```text
POST /ask
  -> SearchService.ask
  -> PgVectorChunkIndex.retrieve
  -> RagAnswerer.answer
  -> OllamaChatClient.generate
  -> RagTraceStore.record_trace
  -> AskResponse
```

No-result behavior:

```text
The answer is not available in the indexed documents.
```

Prompt behavior:

- `RagAnswerer.SYSTEM_PROMPT` tells the model to answer only from retrieved
  context and cite sources with plain bracketed numbers like `[1]`.
- Context sections include rank, score, file name, source refs, parent path, and
  parent chunk text.

Citation behavior:

- Citations are dictionaries containing rank, score, file name, file type,
  source refs, parent path, child chunk id, and parent chunk id.

Streaming chat flow:

```text
POST /chat/ask/stream
  -> ChatService.stream_answer
  -> ChatStore.ensure_session
  -> ChatStore.add_message(role=user)
  -> event: session
  -> PgVectorChunkIndex.retrieve
  -> event: retrieval
  -> RagAnswerer.build_messages
  -> OllamaChatClient.stream
  -> event: delta
  -> RagTraceStore.record_trace
  -> ChatStore.add_message(role=assistant)
  -> event: complete
```

SSE events currently emitted:

```text
session
retrieval
delta
complete
error
```

Current architectural note: SSE string serialization currently lives in
`ChatService.sse_event`, not solely in the API layer.

## Current Search Flow

Retrieval flow:

```text
SearchService.search
  -> PgVectorChunkIndex.retrieve
  -> query embedding via LocalSentenceTransformerEmbeddingProvider
  -> vector candidate query
  -> lexical candidate query
  -> merge and rerank
  -> RetrievalResult
  -> SearchResponse
```

Search behavior:

- Embedding provider default model: `BAAI/bge-small-en-v1.5`.
- Embedding dimensions default: 384.
- Embeddings are normalized through sentence-transformers.
- Candidate limit is `min(max(top_k * 8, 50), 200)`.
- Vector search uses pgvector cosine distance ordering with `<=>`.
- Lexical search uses PostgreSQL `websearch_to_tsquery('english', query)` over
  child text, parent text, and file name.
- Hybrid weights default to vector `0.62`, lexical `0.30`, phrase `0.08`.
- If there are no lexical hits, the score is the vector score.
- Filters are exact match filters for `file_name`, `file_type`, and
  `document_id`.
- Parent context is loaded from stored `parent_chunks.chunk_json`.

Current architectural note: vector search, lexical search, hybrid merge,
document persistence, chunk persistence, schema creation, and admin document
queries all live in `PgVectorChunkIndex`.

## Current Ingestion Flow

API upload flow:

```text
POST /admin/ingestion/jobs
  -> write UploadFile objects to DOCU_SEARCH_UPLOAD_ROOT or storage/uploads
  -> sanitize file names
  -> validate extension, size, and content type
  -> IngestionJobService.create_job
  -> if INGESTION_RUN_MODE=background, FastAPI BackgroundTasks runs job
  -> if INGESTION_RUN_MODE=worker, job remains queued
```

Job execution flow:

```text
IngestionJobService.run_job
  -> IngestionJobStore.mark_running
  -> IngestionOrchestrator.ingest
  -> discover input paths
  -> parse each file through ParserFactory
  -> normalize through parser/base normalizer path
  -> chunk with StructureAwareParentChildChunker
  -> optionally clear index
  -> embed and index with PgVectorChunkIndex.index_documents
  -> read index stats
  -> IngestionJobStore.complete_job or fail_job
```

Supported parser extensions:

```text
.txt
.md
.markdown
.pdf
.docx
.pptx
.xlsx
.csv
.json
```

Ignored ingestion files:

```text
~$*
```

Chunking:

- Strategy: `structure_aware_parent_child`.
- Parent and child chunk ids are deterministic SHA-256 based ids.
- Approximate whitespace token counting is used.
- Parent chunks preserve section structure.
- Child chunks retain `parent_chunk_id`, source block ids, source refs, and
  parent path.

## Tables, Migrations, And Indexes

Migration files on disk:

```text
backend/migrations/001_pgvector_chunk_index.sql
backend/migrations/002_remove_evaluation_feature.sql
```

Actual `schema_migrations` table:

```text
001 001_pgvector_chunk_index.sql checksum prefix 94cc0b3183fa
```

Baseline drift:

- `002_remove_evaluation_feature.sql` exists on disk but is not applied in the
  current database.
- The `evaluation_runs` table and its indexes still exist in the current
  database.
- API tests confirm evaluation routes now return 404.

Actual public tables:

```text
chat_messages
chat_sessions
child_chunks
child_embeddings
documents
evaluation_runs
index_metadata
ingestion_jobs
parent_chunks
rag_traces
schema_migrations
```

Important indexes:

```text
idx_child_embeddings_embedding_hnsw
idx_child_chunks_text_fts
idx_parent_chunks_text_fts
idx_documents_file_name
idx_documents_file_type
idx_ingestion_jobs_status_created
idx_rag_traces_created
idx_rag_traces_query_fts
idx_chat_sessions_updated
idx_chat_messages_session_created
```

## Environment Variables

Variables documented by `.env.example` and/or read by code:

```text
DATABASE_URL
DATABASE_CONNECT_TIMEOUT_SECONDS
DOCU_SEARCH_SKIP_DOTENV
EMBEDDING_PROVIDER
LOCAL_EMBEDDING_MODEL
LOCAL_EMBEDDING_DIMENSIONS
LOCAL_EMBEDDING_DEVICE
LOCAL_EMBEDDING_BATCH_SIZE
DOCU_SEARCH_UPLOAD_ROOT
INGESTION_RUN_MODE
HYBRID_VECTOR_WEIGHT
HYBRID_LEXICAL_WEIGHT
HYBRID_PHRASE_WEIGHT
OLLAMA_HOST
OLLAMA_MODEL
OLLAMA_TEMPERATURE
API_CORS_ORIGINS
API_RATE_LIMIT_PER_MINUTE
MAX_UPLOAD_FILES
MAX_UPLOAD_FILE_SIZE_BYTES
LOG_LEVEL
ADMIN_API_TOKEN
VITE_API_BASE_URL
VITE_ADMIN_TOKEN
```

Current config behavior:

- `load_environment()` searches upward from cwd and `app/core/env.py`.
- Explicit process variables are not overridden.
- Settings are currently read through scattered `os.getenv()` calls.
- There is no centralized typed settings object yet.

## CLI Commands

Installed backend scripts from `backend/pyproject.toml`:

```text
docu-ingest             scripts.ingest_documents:main
docu-chunk              scripts.chunk_documents:main
docu-ask                scripts.ask_index:main
docu-clear-db           scripts.clear_database:main
docu-index              scripts.index_chunks:main
docu-parse              scripts.parse_documents:main
docu-query              scripts.query_index:main
docu-migrate-db         scripts.migrate_database:main
docu-ingestion-worker   scripts.run_ingestion_worker:main
```

Makefile commands:

```text
test
db-up
db-down
db-logs
ingest-corpus
index-corpus
query-corpus
```

## External Integrations

Runtime technologies:

```text
FastAPI
PostgreSQL
pgvector
psycopg
sentence-transformers
Ollama
local filesystem uploads and source files
Docker Compose pgvector/pgvector:pg16
React/Vite frontend
```

## Existing Tests

Current backend test files:

```text
tests/api/test_app.py
tests/core/test_clear_database_cli.py
tests/core/test_env.py
tests/ingestion/test_additional_parsers.py
tests/ingestion/test_block_validator.py
tests/ingestion/test_chunk_documents_cli.py
tests/ingestion/test_document_normalizer.py
tests/ingestion/test_file_validator.py
tests/ingestion/test_ingestion_orchestrator.py
tests/ingestion/test_inspect_parser_output_cli.py
tests/ingestion/test_markdown_parser.py
tests/ingestion/test_parent_child_chunker.py
tests/ingestion/test_parser_factory.py
tests/ingestion/test_pipeline_testing.py
tests/ingestion/test_text_parser.py
tests/search/test_production_embedding_pgvector_and_rag.py
```

Coverage emphasis:

- API route compatibility with fake dependencies.
- Environment loading.
- File validation and parser selection.
- Text, Markdown, CSV, JSON, DOCX, PPTX, XLSX, and PDF parsing.
- Document normalization.
- Parent-child chunking.
- Ingestion orchestration and continue-on-error behavior.
- Pipeline node testing.
- PgVector initialization error behavior.
- RAG answer prompt/citation behavior with fake Ollama clients.

Known test environment requirement:

- Use the backend `.venv`.
- Use a repo-local `--basetemp` on this machine because the default Windows
  pytest temp directory is inaccessible.

## Frontend Expectations

Frontend API base:

```text
VITE_API_BASE_URL=/api
```

Vite dev proxy:

```text
/api/* -> http://127.0.0.1:8001/*
```

Frontend API client paths:

```text
GET    /health
GET    /documents
GET    /documents/{document_id}/source
POST   /search
POST   /ask
GET    /chat/sessions
POST   /chat/sessions
GET    /chat/sessions/{session_id}
DELETE /chat/sessions/{session_id}
POST   /chat/ask
POST   /chat/ask/stream
POST   /admin/index/clear
GET    /admin/overview
GET    /admin/metrics
GET    /admin/documents/{document_id}/chunks
DELETE /admin/documents/{document_id}
POST   /admin/documents/{document_id}/reindex
POST   /admin/ingestion/jobs
GET    /admin/ingestion/jobs
GET    /admin/ingestion/jobs/{job_id}
POST   /admin/pipeline/test
GET    /admin/traces
GET    /admin/traces/{trace_id}
DELETE /admin/traces
```

Frontend SSE handling expects:

```text
event: session
event: retrieval
event: delta
event: complete
event: error
```

Frontend request wrapper sends `X-Admin-Token` when `VITE_ADMIN_TOKEN` is set.

## Large Classes And Mixed Responsibilities

Primary refactor targets:

```text
PgVectorChunkIndex
  - schema creation
  - migration-like table creation
  - document persistence
  - chunk persistence
  - embedding generation
  - vector search
  - lexical search
  - hybrid ranking
  - admin document listing/chunk inspection/delete

ChatService
  - chat workflow coordination
  - retrieval and generation coordination
  - trace recording
  - chat persistence coordination
  - SSE event string serialization

backend/app/api/routes/ingestion.py
  - upload limits
  - filename sanitization
  - file writes
  - parser extension checks
  - validation
  - job creation
  - background task selection

backend/app/api/routes/documents.py
  - document listing response mapping
  - source file path resolution
  - FileResponse construction
  - delete/reindex workflow coordination

AdminOverviewService
  - dashboard aggregation
  - raw SQL query summaries
  - health/risk response composition

IngestionJobStore, ChatStore, RagTraceStore
  - repository-like persistence
  - table initialization
  - row mapping
```

Configuration hotspots:

```text
backend/app/main.py
backend/app/api/dependencies.py
backend/app/api/middleware.py
backend/app/api/routes/documents.py
backend/app/api/routes/health.py
backend/app/api/routes/ingestion.py
backend/app/db/connection.py
backend/app/indexing/pgvector_index.py
backend/app/ingestion/jobs.py
backend/app/llm/ollama_client.py
backend/app/embeddings/local_sentence_transformer.py
backend/app/cli/*.py
```

## Initial Old-To-Target Mapping

This is a planning map only. No code has been moved yet.

```text
PgVectorChunkIndex
  -> repositories/document_repository.py
  -> repositories/chunk_repository.py
  -> repositories/search_repository.py
  -> integrations/search/pgvector_search.py
  -> integrations/search/lexical_search.py
  -> integrations/search/hybrid_search.py
  -> integrations/database/connection.py

ChatStore
  -> repositories/chat_repository.py

IngestionJobStore
  -> repositories/job_repository.py

RagTraceStore
  -> repositories/trace_repository.py

RagAnswerer
  -> rag/context_builder.py
  -> rag/prompt_builder.py
  -> rag/answer_generator.py
  -> rag/citation_validator.py
  -> rag/orchestrator.py

IngestionOrchestrator
  -> ingestion/orchestrator.py remains, with narrower collaborators
  -> ingestion/indexer.py
  -> ingestion/validators/file_validator.py
  -> ingestion/parsers/*
  -> ingestion/normalizers/*
  -> ingestion/chunking/*

api/dependencies.py
  -> core/config.py
  -> bootstrap/container.py
  -> api/dependencies.py as thin dependency adapter
```

## Pre-Existing Risks And Drift

- `002_remove_evaluation_feature.sql` is present but not applied to the current
  database.
- `evaluation_runs` still exists in the current database, although evaluation
  API routes are removed and tests expect 404 for them.
- The root `README.md` is empty.
- Some existing docs contain stale module names, for example references to
  earlier schema or route helper names.
- Docker commands are blocked by current local permissions.
- The global Python is not a valid test environment for this backend.
- The default Windows pytest temp path is inaccessible on this machine.
- There is no centralized typed settings object.
- There is no shared database connection pool.
- Several stores create tables at runtime as well as migrations defining the
  same schema.
- `ChatService` currently formats raw SSE protocol strings, which is an API
  responsibility in the target architecture.

# Frontend API Reference

This document lists the HTTP APIs exposed by the backend and used by the React
frontend. It is based on:

- `frontend/src/services/api.ts`
- `frontend/src/services/types.ts`
- `backend/app/api/router.py`
- `backend/app/api/routes/*.py`
- `backend/app/schemas/api.py`

## Common Rules

Frontend base URL:

```text
VITE_API_BASE_URL=/api
```

In local Vite development, `/api` is proxied to:

```text
http://127.0.0.1:8001
```

Backend admin protection:

- Public routes do not require `X-Admin-Token`.
- Admin routes are protected by `require_admin` in `backend/app/api/dependencies.py`.
- If `ADMIN_API_TOKEN` is empty, admin routes are open for local development.
- If `ADMIN_API_TOKEN` is set, frontend must set `VITE_ADMIN_TOKEN` to the same value.
- The frontend request wrapper sends `X-Admin-Token` automatically when `VITE_ADMIN_TOKEN` exists.

Common JSON error response:

```json
{
  "code": "ERROR_CODE",
  "message": "Human readable message",
  "details": {}
}
```

Common middleware behavior:

- `RequestContextMiddleware` adds `X-Request-ID`, logs request metadata, and records in-process metrics.
- `InMemoryRateLimitMiddleware` rate limits all non-root and non-health routes using `API_RATE_LIMIT_PER_MINUTE`.

## Shared Response Shapes

These shapes appear repeatedly below.

### DocumentSummary

```json
{
  "id": "document-id",
  "title": "Document title",
  "file_name": "source.md",
  "file_type": "md",
  "source_path": "C:/path/source.md",
  "parent_chunk_count": 3,
  "child_chunk_count": 7,
  "created_at": "2026-06-19T10:00:00Z",
  "updated_at": "2026-06-19T10:00:00Z",
  "metadata": {}
}
```

### RetrievedChunkResponse

```json
{
  "rank": 1,
  "score": 0.91,
  "document_id": "document-id",
  "file_name": "source.md",
  "file_type": "md",
  "source_refs": ["lines 10-14"],
  "parent_path": ["Policy", "Security"],
  "child_chunk_id": "child-id",
  "parent_chunk_id": "parent-id",
  "child_text": "Precise matched chunk text",
  "parent_text": "Larger context text used for answering"
}
```

### SearchResponse

```json
{
  "query": "question text",
  "embedding_model": "local-sentence-transformers-BAAI/bge-small-en-v1.5-384d",
  "top_k": 5,
  "results": ["RetrievedChunkResponse[]"],
  "metadata": {
    "retrieval_mode": "hybrid_vector_full_text",
    "hybrid_weights": {
      "vector": 0.62,
      "lexical": 0.3,
      "phrase": 0.08
    }
  }
}
```

### AskResponse

```json
{
  "query": "question text",
  "answer": "Generated answer with citations.",
  "llm_model": "ollama-gpt-oss:120b-cloud",
  "retrieval": "SearchResponse",
  "citations": [],
  "trace_id": "trace-id"
}
```

### IngestionJob

```json
{
  "id": "job-id",
  "status": "queued | running | completed | failed",
  "source_kind": "upload",
  "source_paths": ["storage/uploads/.../file.md"],
  "file_count": 1,
  "discovered_input_files": 1,
  "parsed_document_count": 1,
  "chunked_document_count": 1,
  "parent_chunk_count": 3,
  "child_chunk_count": 7,
  "indexed_child_count": 7,
  "failure_count": 0,
  "timings_ms": {},
  "events": [],
  "error_code": null,
  "error_message": null,
  "error_details": {},
  "options": {},
  "created_at": "2026-06-19T10:00:00Z",
  "updated_at": "2026-06-19T10:00:00Z",
  "started_at": null,
  "completed_at": null
}
```

## Frontend-Used APIs

### 1. GET `/health`

Purpose:

Returns backend readiness for database, embedding provider, and LLM configuration.
The frontend uses this for global status cards and sidebar health.

Frontend caller:

- `getHealth()`
- Used by `AppDataContext`, `AppShell`, `AdminLayout`, `AdminOverviewPage`.

Auth:

- Public.

Request:

```http
GET /health
```

Response:

```json
{
  "status": "ok",
  "service": "docu-search-backend",
  "database": {
    "status": "ok",
    "details": {
      "pgvector_available": true,
      "pgvector_version": "0.x",
      "tables": {
        "documents": true,
        "parent_chunks": true,
        "child_chunks": true,
        "child_embeddings": true
      }
    }
  },
  "embedding": {
    "status": "ok",
    "details": {
      "provider": "local-sentence-transformers-BAAI/bge-small-en-v1.5-384d",
      "model": "BAAI/bge-small-en-v1.5",
      "dimensions": 384,
      "device": "cpu"
    }
  },
  "llm": {
    "status": "ok",
    "details": {
      "provider": "ollama",
      "model": "gpt-oss:120b-cloud",
      "host": "http://localhost:11434"
    }
  }
}
```

Backend involved:

- Route: `backend/app/api/routes/health.py::health_check`
- Dependencies: `get_database_url`, `get_embedding_provider`, `get_llm_client`
- Services: `check_database_health`, `LocalSentenceTransformerEmbeddingProvider`, `OllamaChatClient`
- Env: `DATABASE_URL`, `LOCAL_EMBEDDING_MODEL`, `LOCAL_EMBEDDING_DIMENSIONS`, `LOCAL_EMBEDDING_DEVICE`, `OLLAMA_HOST`, `OLLAMA_MODEL`
- DB touched: non-mutating health queries against PostgreSQL and pgvector.

### 2. GET `/documents`

Purpose:

Lists indexed documents and chunk counts. The frontend uses it for the sidebar
document count, admin summary cards, and index inventory.

Frontend caller:

- `getDocuments()`
- Used by `AppDataContext`, `AdminIndexPage`, overview/status UI.

Auth:

- Public.

Request:

```http
GET /documents?limit=100&offset=0
```

Query params:

```json
{
  "limit": "integer, default 100, min 1, max 500",
  "offset": "integer, default 0, min 0"
}
```

Response:

```json
{
  "total": 1,
  "limit": 100,
  "offset": 0,
  "documents": ["DocumentSummary[]"]
}
```

Backend involved:

- Route: `backend/app/api/routes/documents.py::list_documents`
- Dependency: `get_chunk_index`
- Service: `PgVectorChunkIndex.stats`, `PgVectorChunkIndex.list_documents`
- Env: `DATABASE_URL`, embedding model env values for index initialization checks
- DB touched: `documents`, `parent_chunks`, `child_chunks`, `child_embeddings`, `index_metadata`

### 3. POST `/search`

Purpose:

Runs retrieval only. It returns ranked source chunks without generating an LLM
answer. The admin test bench uses it to debug search quality.

Frontend caller:

- `searchDocuments(payload)`
- Used by `AdminWorkbenchContext`, `AdminTestBenchPage`.

Auth:

- Public.

Request:

```json
{
  "query": "Which policy mentions the 14-day satellite-mode exception?",
  "top_k": 5,
  "file_name": "optional exact file name",
  "file_type": "optional file type such as md",
  "document_id": "optional document id"
}
```

Validation:

- `query`: required, non-empty after trimming
- `top_k`: default 5, min 1, max 50
- filters are optional exact-match filters

Response:

```json
"SearchResponse"
```

Backend involved:

- Route: `backend/app/api/routes/search.py::search_index`
- Dependency: `get_chunk_index`
- Service: `PgVectorChunkIndex.retrieve`
- Embedding: embeds the query using `LocalSentenceTransformerEmbeddingProvider`
- Retrieval: hybrid vector search plus PostgreSQL full-text search
- Env: `DATABASE_URL`, `LOCAL_EMBEDDING_*`, `HYBRID_VECTOR_WEIGHT`, `HYBRID_LEXICAL_WEIGHT`, `HYBRID_PHRASE_WEIGHT`
- DB touched: `index_metadata`, `documents`, `parent_chunks`, `child_chunks`, `child_embeddings`

### 4. POST `/ask`

Purpose:

Runs retrieval, sends retrieved parent context to the LLM, stores a RAG trace,
and returns the grounded answer plus citations.

Frontend caller:

- `askDocuments(payload)`
- Used by `AdminWorkbenchContext`, `AdminTestBenchPage`.

Auth:

- Public.

Request:

```json
{
  "query": "Which policy mentions the 14-day satellite-mode exception?",
  "top_k": 5,
  "file_name": "optional exact file name",
  "file_type": "optional file type such as md",
  "document_id": "optional document id"
}
```

Response:

```json
"AskResponse"
```

Backend involved:

- Route: `backend/app/api/routes/search.py::ask_index`
- Dependencies: `get_chunk_index`, `get_rag_answerer`, `get_rag_trace_store`
- Services: `PgVectorChunkIndex.retrieve`, `RagAnswerer.answer`, `OllamaChatClient.generate`, `RagTraceStore.record_trace`
- Env: `DATABASE_URL`, `LOCAL_EMBEDDING_*`, `HYBRID_*`, `OLLAMA_HOST`, `OLLAMA_MODEL`, `OLLAMA_TEMPERATURE`
- DB touched: retrieval tables plus `rag_traces`

### 5. GET `/chat/sessions`

Purpose:

Lists saved chat sessions for the chat sidebar.

Frontend caller:

- `listChatSessions()`
- Used by `ChatPanel`.

Auth:

- Public.

Request:

```http
GET /chat/sessions?limit=30&offset=0
```

Query params:

```json
{
  "limit": "integer, default 30, min 1, max 100",
  "offset": "integer, default 0, min 0"
}
```

Response:

```json
{
  "total": 1,
  "limit": 30,
  "offset": 0,
  "sessions": [
    {
      "id": "session-id",
      "title": "Chat title",
      "message_count": 2,
      "created_at": "2026-06-19T10:00:00Z",
      "updated_at": "2026-06-19T10:05:00Z"
    }
  ]
}
```

Backend involved:

- Route: `backend/app/api/routes/chat.py::list_chat_sessions`
- Dependency: `get_chat_store`
- Service: `ChatStore.list_sessions`
- Env: `DATABASE_URL`
- DB touched: `chat_sessions`, `chat_messages`

### 6. POST `/chat/sessions`

Purpose:

Creates an empty chat session. The current chat UI mostly creates sessions
implicitly during ask, but this API is available in the frontend client.

Frontend caller:

- `createChatSession(title?)`

Auth:

- Public.

Request:

```json
{
  "title": "Optional title up to 160 characters"
}
```

Response:

```json
{
  "id": "session-id",
  "title": "Optional title",
  "message_count": 0,
  "created_at": "2026-06-19T10:00:00Z",
  "updated_at": "2026-06-19T10:00:00Z"
}
```

Backend involved:

- Route: `backend/app/api/routes/chat.py::create_chat_session`
- Dependency: `get_chat_store`
- Service: `ChatStore.create_session`
- DB touched: `chat_sessions`

### 7. GET `/chat/sessions/{session_id}`

Purpose:

Loads one chat session and its full message history.

Frontend caller:

- `getChatSession(sessionId)`
- Used by `ChatPanel`.

Auth:

- Public.

Request:

```http
GET /chat/sessions/{session_id}
```

Response:

```json
{
  "id": "session-id",
  "title": "Chat title",
  "message_count": 2,
  "created_at": "2026-06-19T10:00:00Z",
  "updated_at": "2026-06-19T10:05:00Z",
  "messages": [
    {
      "id": "message-id",
      "session_id": "session-id",
      "role": "user",
      "content": "Question text",
      "trace_id": null,
      "llm_model": null,
      "latency_ms": null,
      "sources": [],
      "created_at": "2026-06-19T10:01:00Z"
    },
    {
      "id": "message-id",
      "session_id": "session-id",
      "role": "assistant",
      "content": "Answer text",
      "trace_id": "trace-id",
      "llm_model": "ollama-gpt-oss:120b-cloud",
      "latency_ms": 1234.5,
      "sources": ["RetrievedChunkResponse[]"],
      "created_at": "2026-06-19T10:01:05Z"
    }
  ]
}
```

Backend involved:

- Route: `backend/app/api/routes/chat.py::get_chat_session`
- Dependency: `get_chat_store`
- Service: `ChatStore.get_session`
- DB touched: `chat_sessions`, `chat_messages`

### 8. DELETE `/chat/sessions/{session_id}`

Purpose:

Deletes a chat session and its messages.

Frontend caller:

- `deleteChatSession(sessionId)`

Auth:

- Public.

Request:

```http
DELETE /chat/sessions/{session_id}
```

Response:

```json
{
  "status": "deleted",
  "session_id": "session-id"
}
```

Backend involved:

- Route: `backend/app/api/routes/chat.py::delete_chat_session`
- Dependency: `get_chat_store`
- Service: `ChatStore.delete_session`
- DB touched: `chat_sessions`, cascade deletes `chat_messages`

### 9. POST `/chat/ask`

Purpose:

Non-streaming chat ask. It creates or reuses a chat session, stores the user
message, retrieves context, generates an answer, records a RAG trace, stores the
assistant message, and returns all final objects.

Frontend caller:

- `askChat(payload)`
- Present in frontend API client. The active chat UI currently uses the streaming variant instead.

Auth:

- Public.

Request:

```json
{
  "query": "Which policy mentions the 14-day satellite-mode exception?",
  "top_k": 5,
  "file_name": "optional exact file name",
  "file_type": "optional file type such as md",
  "document_id": "optional document id",
  "session_id": "optional existing session id"
}
```

Response:

```json
{
  "session": "ChatSessionSummary",
  "user_message": "ChatMessageResponse",
  "assistant_message": "ChatMessageResponse",
  "answer": "AskResponse"
}
```

Backend involved:

- Route: `backend/app/api/routes/chat.py::ask_chat`
- Dependencies: `get_chunk_index`, `get_rag_answerer`, `get_rag_trace_store`, `get_chat_store`
- Services: `ChatStore`, `PgVectorChunkIndex`, `RagAnswerer`, `OllamaChatClient`, `RagTraceStore`
- DB touched: retrieval tables, `rag_traces`, `chat_sessions`, `chat_messages`

### 10. POST `/chat/ask/stream`

Purpose:

Streaming chat ask for the main user chat UI. It emits Server-Sent Events for
session creation, retrieval results, answer deltas, and completion.

Frontend caller:

- `askChatStream(payload, handlers)`
- Used by `ChatPanel`.

Auth:

- Public.

Request:

```json
{
  "query": "Which policy mentions the 14-day satellite-mode exception?",
  "top_k": 5,
  "file_name": "optional exact file name",
  "file_type": "optional file type such as md",
  "document_id": "optional document id",
  "session_id": "optional existing session id"
}
```

Response content type:

```text
text/event-stream
```

SSE events:

```text
event: session
data: {"session":"ChatSessionSummary","user_message":"ChatMessageResponse"}

event: retrieval
data: "SearchResponse"

event: delta
data: {"text":"partial answer token or text"}

event: complete
data: {"session":"ChatSessionSummary","assistant_message":"ChatMessageResponse","trace_id":"trace-id"}

event: error
data: {"code":"ERROR_CODE","message":"Message"}
```

Backend involved:

- Route: `backend/app/api/routes/chat.py::ask_chat_stream`
- Generator: `stream_chat_answer`
- Dependencies: `get_chunk_index`, `get_rag_answerer`, `get_rag_trace_store`, `get_chat_store`
- Services: `ChatStore`, `PgVectorChunkIndex`, `RagAnswerer.build_messages`, `OllamaChatClient.stream`, `RagTraceStore`
- DB touched: retrieval tables, `rag_traces`, `chat_sessions`, `chat_messages`

### 11. GET `/admin/documents/{document_id}/chunks`

Purpose:

Returns stored child chunks and parent context for a selected indexed document.
Used by the admin index inspector.

Frontend caller:

- `getDocumentChunks(documentId)`
- Used by `AdminIndexPage`.

Auth:

- Admin route.

Request:

```http
GET /admin/documents/{document_id}/chunks?limit=100&offset=0
```

Query params:

```json
{
  "limit": "integer, default 100, min 1, max 500",
  "offset": "integer, default 0, min 0"
}
```

Response:

```json
{
  "document": "DocumentSummary",
  "total": 7,
  "limit": 100,
  "offset": 0,
  "chunks": [
    {
      "child_chunk_id": "child-id",
      "parent_chunk_id": "parent-id",
      "child_index": 0,
      "parent_index": 0,
      "child_text": "Child text",
      "parent_text": "Parent context text",
      "child_token_count": 80,
      "parent_token_count": 450,
      "source_refs": ["lines 10-14"],
      "parent_path": ["Section"],
      "metadata": {},
      "created_at": "2026-06-19T10:00:00Z"
    }
  ]
}
```

Backend involved:

- Route: `backend/app/api/routes/documents.py::list_document_chunks`
- Dependency: `get_chunk_index`
- Services: `PgVectorChunkIndex.get_document`, `PgVectorChunkIndex.list_document_chunks`
- DB touched: `documents`, `parent_chunks`, `child_chunks`

### 12. GET `/documents/{document_id}/source`

Purpose:

Opens the original source file for an indexed document. Chat citations use this
endpoint when retrieved chunks include `document_id`.

Frontend caller:

- Inline citation links in `ChatPanel`.

Auth:

- Public.

Request:

```http
GET /documents/{document_id}/source
```

Response:

```text
Original source file returned inline with the detected media type.
```

Backend involved:

- Route: `backend/app/api/routes/documents.py::open_document_source`
- Dependency: `get_chunk_index`
- Services: `PgVectorChunkIndex.get_document`, `FileResponse`
- DB touched: `documents`
- Filesystem touched: reads the indexed document `source_path`

### 13. DELETE `/admin/documents/{document_id}`

Purpose:

Deletes one indexed document and its parent chunks, child chunks, and embeddings.
Source files are not deleted.

Frontend caller:

- `deleteDocument(documentId)`
- Used by `AdminIndexPage`.

Auth:

- Admin route.

Request:

```http
DELETE /admin/documents/{document_id}
```

Response:

```json
{
  "status": "deleted",
  "document_id": "document-id"
}
```

Backend involved:

- Route: `backend/app/api/routes/documents.py::delete_document`
- Dependency: `get_chunk_index`
- Service: `PgVectorChunkIndex.delete_document`
- DB touched: `child_embeddings`, `child_chunks`, `parent_chunks`, `documents`

### 14. POST `/admin/documents/{document_id}/reindex`

Purpose:

Creates an ingestion job to re-index an existing document from its saved
`source_path`.

Frontend caller:

- `reindexDocument(documentId)`
- Used by `AdminIndexPage`.

Auth:

- Admin route.

Request:

```http
POST /admin/documents/{document_id}/reindex
```

Response:

```json
{
  "job": "IngestionJob"
}
```

Backend involved:

- Route: `backend/app/api/routes/documents.py::reindex_document`
- Dependencies: `get_chunk_index`, `get_ingestion_job_service`
- Services: `PgVectorChunkIndex.get_document`, `IngestionJobService.create_job`
- Runtime: if `INGESTION_RUN_MODE=background`, FastAPI background task runs `service.run_job`
- Env: `INGESTION_RUN_MODE`
- DB touched: `documents`, `ingestion_jobs`; later ingestion touches chunk/index tables

### 15. POST `/admin/index/clear`

Purpose:

Clears the full index: documents, chunks, and embeddings. It does not delete
source files, chat history, traces, or evaluation runs.

Frontend caller:

- `clearIndex()`
- Used by `AdminWorkbenchContext`, `AdminOpsPage`.

Auth:

- Admin route.

Request:

```json
{
  "confirm": true
}
```

Response:

```json
{
  "status": "cleared",
  "document_count": 0,
  "parent_chunk_count": 0,
  "child_chunk_count": 0
}
```

Backend involved:

- Route: `backend/app/api/routes/admin.py::clear_index`
- Dependency: `get_chunk_index`
- Service: `PgVectorChunkIndex.clear`
- DB touched: deletes from `child_embeddings`, `child_chunks`, `parent_chunks`, `documents`

### 16. GET `/admin/metrics`

Purpose:

Returns in-process API and operation metrics recorded by middleware and parser
operations. Used by the admin ops page.

Frontend caller:

- `getApiMetrics()`
- Used by `AdminOpsPage`.

Auth:

- Admin route.

Request:

```http
GET /admin/metrics
```

Response:

```json
{
  "total_count": 10,
  "success_count": 9,
  "failure_count": 1,
  "success_by_operation": {
    "GET /health": 3
  },
  "failure_by_operation": {},
  "failure_by_code": {},
  "total_duration_ms_by_operation": {
    "GET /health": 12.3
  }
}
```

Backend involved:

- Route: `backend/app/api/routes/admin.py::get_api_metrics`
- Source: `backend/app/api/middleware.py::metrics_snapshot`
- Service: `DEFAULT_OPERATION_METRICS_RECORDER`
- DB touched: none
- Runtime note: in-memory only, resets when backend process restarts

### 17. POST `/admin/ingestion/jobs`

Purpose:

Uploads one or more files, validates them, creates an ingestion job, and either
runs it in the background or leaves it queued for a worker.

Frontend caller:

- `createIngestionJob(options)`
- Used by `AdminIngestionPage`.

Auth:

- Admin route.

Request content type:

```text
multipart/form-data
```

Form fields:

```text
files: one or more uploaded files
clear_index: boolean, default false
replace: boolean, default true
continue_on_error: boolean, default true
```

Supported extensions:

```text
.txt, .md, .markdown, .pdf, .docx, .pptx, .xlsx, .csv, .json
```

Response:

```json
{
  "job": "IngestionJob"
}
```

Backend involved:

- Route: `backend/app/api/routes/ingestion.py::create_ingestion_job`
- Dependency: `get_ingestion_job_service`
- Services: `ParserFactory`, `validate_local_file`, `IngestionJobService.create_job`, optional `IngestionJobService.run_job`
- Runtime path: uploaded files are written under `DOCU_SEARCH_UPLOAD_ROOT` or `storage/uploads`
- Env: `MAX_UPLOAD_FILES`, `MAX_UPLOAD_FILE_SIZE_BYTES`, `DOCU_SEARCH_UPLOAD_ROOT`, `INGESTION_RUN_MODE`
- DB touched: `ingestion_jobs`; if background execution runs, also index tables

### 18. GET `/admin/ingestion/jobs`

Purpose:

Lists ingestion jobs and their statuses for the ingestion page.

Frontend caller:

- `listIngestionJobs()`
- Used by `AdminIngestionPage`.

Auth:

- Admin route.

Request:

```http
GET /admin/ingestion/jobs?limit=20&offset=0
```

Query params:

```json
{
  "limit": "integer, default 20, min 1, max 100",
  "offset": "integer, default 0, min 0"
}
```

Response:

```json
{
  "total": 1,
  "limit": 20,
  "offset": 0,
  "jobs": ["IngestionJob[]"]
}
```

Backend involved:

- Route: `backend/app/api/routes/ingestion.py::list_ingestion_jobs`
- Dependency: `get_ingestion_job_service`
- Service: `IngestionJobStore.list_jobs`
- DB touched: `ingestion_jobs`

### 19. GET `/admin/ingestion/jobs/{job_id}`

Purpose:

Fetches one ingestion job with detailed events, counts, timings, and errors.

Frontend caller:

- `getIngestionJob(jobId)`
- Used by `AdminIngestionPage`.

Auth:

- Admin route.

Request:

```http
GET /admin/ingestion/jobs/{job_id}
```

Response:

```json
"IngestionJob"
```

Backend involved:

- Route: `backend/app/api/routes/ingestion.py::get_ingestion_job`
- Dependency: `get_ingestion_job_service`
- Service: `IngestionJobStore.get_job`
- DB touched: `ingestion_jobs`

### 19A. POST `/admin/pipeline/test`

Purpose:

Runs one bounded, non-destructive pipeline layer test against an uploaded document.
Supported stages are `validate`, `parse`, `chunk`, `embed`, and `index`.

Frontend caller:

- `testPipelineNode(stage, file)`
- Used by `AdminTestBenchPage` (Pipeline Lab).

Auth:

- Admin route.

Request:

```http
POST /admin/pipeline/test
Content-Type: multipart/form-data

stage=parse
file=<document>
```

Response:

```json
{
  "stage": "parse",
  "status": "completed",
  "duration_ms": 12.4,
  "summary": {
    "parser": "MarkdownParser",
    "block_count": 8,
    "normalization": "completed"
  },
  "preview": []
}
```

Backend involved:

- Route: `backend/app/api/routes/pipeline.py::test_pipeline_node`
- Service: `PipelineNodeTester`
- Production layers reused: file validation, parser/normalizer, chunker, embedding provider, pgvector stats
- DB mutation: none

### 20. GET `/admin/evaluation/cases`

Purpose:

Returns built-in RAG evaluation cases for the admin evaluation page.

Frontend caller:

- `listEvaluationCases()`
- Used by `AdminEvaluationPage`.

Auth:

- Admin route.

Request:

```http
GET /admin/evaluation/cases
```

Response:

```json
[
  {
    "id": "satellite-mode-exception",
    "question": "Which policy mentions the 14-day satellite-mode exception?",
    "expected_answer_terms": ["P-004", "Password rotation exception", "14 days"],
    "expected_context_terms": ["P-004", "14 days", "satellite mode"],
    "expected_source_files": ["02_aquila_product_knowledge_base.md"],
    "tags": ["policy", "exact-value", "source"]
  }
]
```

Backend involved:

- Route: `backend/app/api/routes/evaluation.py::list_evaluation_cases`
- Source: `backend/app/evaluation/dataset.py::BUILTIN_EVALUATION_CASES`
- DB touched: none

### 21. POST `/admin/evaluation/run`

Purpose:

Runs selected built-in evaluation cases against the current index, optionally
generates answers, calculates pass/fail metrics, and stores the evaluation run.

Frontend caller:

- `runEvaluation(payload)`
- Used by `AdminEvaluationPage`.

Auth:

- Admin route.

Request:

```json
{
  "top_k": 5,
  "include_answers": true,
  "case_ids": ["satellite-mode-exception"]
}
```

Validation:

- `top_k`: default 5, min 1, max 20
- `include_answers`: default true
- `case_ids`: optional. If omitted, all built-in cases run.

Response:

```json
{
  "top_k": 5,
  "include_answers": true,
  "summary": {
    "total_cases": 1,
    "passed_cases": 1,
    "failed_cases": 0,
    "retrieval_passed_cases": 1,
    "answer_passed_cases": 1,
    "source_hit_rate": 1.0,
    "answer_term_pass_rate": 1.0,
    "mean_retrieval_ms": 25.0,
    "mean_answer_ms": 1200.0,
    "mean_total_ms": 1225.0
  },
  "cases": ["EvaluationCase[]"],
  "results": [
    {
      "case_id": "satellite-mode-exception",
      "question": "Question text",
      "status": "passed",
      "retrieval_passed": true,
      "answer_passed": true,
      "source_rank": 1,
      "missing_context_terms": [],
      "missing_answer_terms": [],
      "answer": "Answer text",
      "llm_model": "ollama-gpt-oss:120b-cloud",
      "retrieval_ms": 25.0,
      "answer_ms": 1200.0,
      "total_ms": 1225.0,
      "contexts": [],
      "citations": []
    }
  ]
}
```

Backend involved:

- Route: `backend/app/api/routes/evaluation.py::run_evaluation`
- Dependencies: `get_chunk_index`, `get_rag_answerer`, `get_evaluation_history_store`
- Services: `EvaluationRunner.run`, `PgVectorChunkIndex.retrieve`, optional `RagAnswerer.answer`, `EvaluationHistoryStore.record_run`
- Env: database, embedding, hybrid, and optionally Ollama env when `include_answers=true`
- DB touched: retrieval tables and `evaluation_runs`

### 22. GET `/admin/evaluation/runs`

Purpose:

Lists saved evaluation run summaries.

Frontend caller:

- `listEvaluationRuns()`
- Used by `AdminEvaluationPage`.

Auth:

- Admin route.

Request:

```http
GET /admin/evaluation/runs?limit=20&offset=0
```

Response:

```json
{
  "total": 1,
  "limit": 20,
  "offset": 0,
  "runs": [
    {
      "id": "run-id",
      "top_k": 5,
      "include_answers": true,
      "total_cases": 8,
      "passed_cases": 8,
      "failed_cases": 0,
      "source_hit_rate": 1.0,
      "answer_term_pass_rate": 1.0,
      "mean_total_ms": 1234.5,
      "created_at": "2026-06-19T10:00:00Z"
    }
  ]
}
```

Backend involved:

- Route: `backend/app/api/routes/evaluation.py::list_evaluation_runs`
- Dependency: `get_evaluation_history_store`
- Service: `EvaluationHistoryStore.list_runs`
- DB touched: `evaluation_runs`

### 23. GET `/admin/traces`

Purpose:

Lists saved RAG traces for admin inspection.

Frontend caller:

- `listRagTraces()`
- Used by `AdminTracesPage`.

Auth:

- Admin route.

Request:

```http
GET /admin/traces?limit=25&offset=0
```

Query params:

```json
{
  "limit": "integer, default 25, min 1, max 100",
  "offset": "integer, default 0, min 0"
}
```

Response:

```json
{
  "total": 1,
  "limit": 25,
  "offset": 0,
  "traces": [
    {
      "id": "trace-id",
      "query": "Question text",
      "answer": "Answer text",
      "llm_model": "ollama-gpt-oss:120b-cloud",
      "embedding_model": "local-sentence-transformers-BAAI/bge-small-en-v1.5-384d",
      "top_k": 5,
      "result_count": 5,
      "retrieval_ms": 25.0,
      "answer_ms": 1200.0,
      "total_ms": 1225.0,
      "created_at": "2026-06-19T10:00:00Z"
    }
  ]
}
```

Backend involved:

- Route: `backend/app/api/routes/traces.py::list_traces`
- Dependency: `get_rag_trace_store`
- Service: `RagTraceStore.list_traces`
- DB touched: `rag_traces`

### 24. GET `/admin/traces/{trace_id}`

Purpose:

Returns a full RAG trace including query, answer, retrieval response, citations,
timings, and metadata.

Frontend caller:

- `getRagTrace(traceId)`
- Used by `AdminTracesPage`.

Auth:

- Admin route.

Request:

```http
GET /admin/traces/{trace_id}
```

Response:

```json
{
  "id": "trace-id",
  "query": "Question text",
  "answer": "Answer text",
  "llm_model": "ollama-gpt-oss:120b-cloud",
  "embedding_model": "local-sentence-transformers-BAAI/bge-small-en-v1.5-384d",
  "top_k": 5,
  "result_count": 5,
  "retrieval_ms": 25.0,
  "answer_ms": 1200.0,
  "total_ms": 1225.0,
  "created_at": "2026-06-19T10:00:00Z",
  "retrieval": "SearchResponse",
  "citations": [],
  "metadata": {
    "route": "/ask"
  }
}
```

Backend involved:

- Route: `backend/app/api/routes/traces.py::get_trace`
- Dependency: `get_rag_trace_store`
- Service: `RagTraceStore.get_trace`
- DB touched: `rag_traces`

### 25. DELETE `/admin/traces`

Purpose:

Clears stored RAG trace history. It does not delete documents, chunks,
embeddings, chat sessions, or evaluation runs.

Frontend caller:

- `clearRagTraces()`
- Used by `AdminTracesPage`.

Auth:

- Admin route.

Request:

```http
DELETE /admin/traces
```

Response:

```json
{
  "status": "deleted",
  "deleted_count": 10
}
```

Backend involved:

- Route: `backend/app/api/routes/traces.py::clear_traces`
- Dependency: `get_rag_trace_store`
- Service: `RagTraceStore.delete_traces`
- DB touched: `rag_traces`

## Backend APIs Not Currently Called By Frontend

These endpoints exist in FastAPI but are not currently called from
`frontend/src/services/api.ts`.

### GET `/`

Purpose:

Minimal service root.

Response:

```json
{
  "service": "docu-search-backend",
  "status": "ok"
}
```

Backend involved:

- Route: inline in `backend/app/main.py::create_app`
- DB touched: none

### GET `/admin/auth/status`

Purpose:

Reports whether admin token protection is enabled.

Auth:

- Admin route, so if `ADMIN_API_TOKEN` is set this endpoint itself requires `X-Admin-Token`.

Request:

```http
GET /admin/auth/status
```

Response:

```json
{
  "admin_token_required": true
}
```

Backend involved:

- Route: `backend/app/api/routes/admin.py::get_admin_auth_status`
- Env: `ADMIN_API_TOKEN`
- DB touched: none

### GET `/admin/evaluation/runs/{run_id}`

Purpose:

Fetches a full saved evaluation run, including the stored response payload.

Auth:

- Admin route.

Request:

```http
GET /admin/evaluation/runs/{run_id}
```

Response:

```json
{
  "id": "run-id",
  "top_k": 5,
  "include_answers": true,
  "total_cases": 8,
  "passed_cases": 8,
  "failed_cases": 0,
  "source_hit_rate": 1.0,
  "answer_term_pass_rate": 1.0,
  "mean_total_ms": 1234.5,
  "created_at": "2026-06-19T10:00:00Z",
  "response": {}
}
```

Backend involved:

- Route: `backend/app/api/routes/evaluation.py::get_evaluation_run`
- Dependency: `get_evaluation_history_store`
- Service: `EvaluationHistoryStore.get_run`
- DB touched: `evaluation_runs`

## Endpoint To Frontend Page Map

```text
Global app data:
  GET /health
  GET /documents

Chat page:
  GET /chat/sessions
  POST /chat/sessions
  GET /chat/sessions/{session_id}
  DELETE /chat/sessions/{session_id}
  POST /chat/ask
  POST /chat/ask/stream
  GET /documents/{document_id}/source

Admin overview:
  GET /health
  GET /documents

Admin test bench:
  POST /admin/pipeline/test
  POST /search
  POST /ask

Admin index:
  GET /documents
  GET /admin/documents/{document_id}/chunks
  DELETE /admin/documents/{document_id}
  POST /admin/documents/{document_id}/reindex

Admin ingestion:
  POST /admin/ingestion/jobs
  GET /admin/ingestion/jobs
  GET /admin/ingestion/jobs/{job_id}

Admin evaluation:
  GET /admin/evaluation/cases
  POST /admin/evaluation/run
  GET /admin/evaluation/runs

Admin traces:
  GET /admin/traces
  GET /admin/traces/{trace_id}
  DELETE /admin/traces

Admin ops:
  POST /admin/index/clear
  GET /admin/metrics
```

## Backend Dependency Map

```text
API routes
  -> dependencies.py
  -> PgVectorChunkIndex
  -> LocalSentenceTransformerEmbeddingProvider
  -> PostgreSQL/pgvector

Ask/chat routes
  -> PgVectorChunkIndex.retrieve
  -> RagAnswerer
  -> OllamaChatClient
  -> RagTraceStore
  -> ChatStore for chat routes

Ingestion routes
  -> Upload validation
  -> IngestionJobService
  -> IngestionOrchestrator
  -> ParserFactory
  -> normalizers
  -> parent-child chunker
  -> PgVectorChunkIndex.index_documents

Evaluation routes
  -> EvaluationRunner
  -> PgVectorChunkIndex.retrieve
  -> optional RagAnswerer
  -> EvaluationHistoryStore

Trace routes
  -> RagTraceStore
```

## Main Environment Variables By API Area

```text
All DB-backed APIs:
  DATABASE_URL
  DATABASE_CONNECT_TIMEOUT_SECONDS

Admin APIs:
  ADMIN_API_TOKEN

Rate limiting and metrics:
  API_RATE_LIMIT_PER_MINUTE
  LOG_LEVEL

Retrieval/search APIs:
  LOCAL_EMBEDDING_MODEL
  LOCAL_EMBEDDING_DIMENSIONS
  LOCAL_EMBEDDING_DEVICE
  LOCAL_EMBEDDING_BATCH_SIZE
  HYBRID_VECTOR_WEIGHT
  HYBRID_LEXICAL_WEIGHT
  HYBRID_PHRASE_WEIGHT

Ask/chat/evaluation answer APIs:
  OLLAMA_HOST
  OLLAMA_MODEL
  OLLAMA_TEMPERATURE

Ingestion APIs:
  DOCU_SEARCH_UPLOAD_ROOT
  INGESTION_RUN_MODE
  MAX_UPLOAD_FILES
  MAX_UPLOAD_FILE_SIZE_BYTES
```

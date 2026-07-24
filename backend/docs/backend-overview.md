# Backend Overview

The backend is a modular monolith for document ingestion, retrieval, and
grounded RAG answers. Public API paths remain unchanged for frontend
compatibility.

## Runtime Flow

```text
Frontend
  -> API endpoint
  -> Service
  -> RAG or ingestion workflow
  -> Repository
  -> Integration
  -> PostgreSQL / pgvector / Ollama / Sentence Transformers
```

## Responsibilities

`app/api` handles FastAPI transport, middleware, dependency adapters, exception
mapping, and SSE wire formatting. Endpoint modules should stay thin and call
services.

`app/schemas` defines request and response contracts.

`app/services` coordinates user-facing operations for search, chat, documents,
ingestion, admin actions, health, and trace inspection.

`app/rag` builds context and prompts, calls the answer generator, validates
citations, and keeps the `RagAnswerer` facade.

`app/ingestion` validates files, selects parsers, normalizes parsed content,
chunks documents, and runs the ingestion orchestrator.

`app/repositories` owns persistence-facing application data access: documents,
chunks, index metadata/stats, search coordination, jobs, traces, and chat.
`PgVectorChunkIndex` remains as the compatibility facade while delegating to
focused repositories.

`app/integrations` contains technology-specific adapters for PostgreSQL,
pgvector search, full-text search, hybrid ranking, sentence-transformers, and
Ollama.

`app/bootstrap` creates the application container, shared database pool, and
startup checks.

`app/lifespan.py` attaches the container, records startup checks, and closes
shared resources.

`app/workers` contains the task execution boundary for background ingestion.

`app/observability` owns in-process operation metrics. Compatibility imports
remain in `app.core.observability`.

## Main Flows

Search:

```text
POST /search
  -> SearchService
  -> PgVectorChunkIndex.retrieve
  -> SearchRepository
  -> PgVectorSearch + LexicalSearch + HybridSearchRanker
```

Answer generation:

```text
POST /ask or /chat/ask
  -> SearchService / ChatService
  -> retrieval
  -> RagAnswerer
  -> RagContextBuilder
  -> RagPromptBuilder
  -> AnswerGenerator
  -> OllamaChatClient
  -> CitationValidator
  -> TraceRepository
```

Ingestion:

```text
POST /admin/ingestion/jobs
  -> IngestionService
  -> JobRepository
  -> TaskExecutor
  -> IngestionJobService
  -> IngestionOrchestrator
  -> parsers / normalizers / chunker
  -> PgVectorChunkIndex
```

Chat streaming:

```text
POST /chat/ask/stream
  -> ChatService.stream_answer
  -> session event
  -> retrieval event
  -> delta events
  -> complete or error event
```

## What Not To Put Where

Do not put SQL, parser logic, embedding calls, or Ollama calls in `app/api`.

Do not put FastAPI imports in `app/rag` or `app/ingestion`.

Do not put API imports in `app/repositories` or `app/integrations`.

Do not put feature services or business workflows in `app/core`.

## Docker Shape

The Docker Compose stack contains:

```text
postgres    pgvector PostgreSQL
migrations  one-shot SQL migration runner
backend     FastAPI API process
frontend    Nginx static frontend + /api proxy
```

Docker uses an internal database URL:

```text
postgresql://...@postgres:5432/...
```

Local development can still use the host-mapped PostgreSQL port:

```text
postgresql://...@127.0.0.1:55432/...
```

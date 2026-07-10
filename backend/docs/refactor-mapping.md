# Refactor Mapping

This document maps major old responsibilities to the current modular locations.

## Configuration

```text
Scattered os.getenv reads
  -> app.core.config.AppSettings
  -> app.core.config.get_settings()
```

Compatibility note: CLI argument defaults still read environment variables
directly where preserving command-line behavior is clearer.

## Bootstrap

```text
Route-level dependency construction
  -> app.bootstrap.container.ApplicationContainer
  -> app.lifespan.lifespan
  -> app.api.dependencies
```

FastAPI dependency overrides remain available in tests.

## Documents And Admin

```text
Document route business logic
  -> app.repositories.document_repository.DocumentRepository
  -> app.services.document_service.DocumentService

Admin clear-index route logic
  -> app.services.admin_service.AdminService
```

## Search

```text
PgVectorChunkIndex vector SQL
  -> app.integrations.search.pgvector_search.PgVectorSearch

PgVectorChunkIndex lexical SQL
  -> app.integrations.search.lexical_search.LexicalSearch

PgVectorChunkIndex hybrid scoring
  -> app.integrations.search.hybrid_search.HybridSearchRanker

app.search.service.SearchService
  -> app.services.search_service.SearchService

Search response helpers
  -> app.services.search_mapping
```

The old `app.search` package has been removed.

## RAG

```text
RagAnswerer context building
  -> app.rag.context_builder.RagContextBuilder

RagAnswerer prompt construction
  -> app.rag.prompt_builder.RagPromptBuilder

RagAnswerer LLM call
  -> app.rag.answer_generator.AnswerGenerator

RagAnswerer citation mapping
  -> app.rag.citation_validator.CitationValidator
```

`RagAnswerer` remains the public facade.

## Ingestion

```text
Upload validation and file persistence in API route
  -> app.services.ingestion_service.IngestionService

Job persistence and execution
  -> app.ingestion.jobs.IngestionJobStore
  -> app.ingestion.jobs.IngestionJobService

Pipeline execution
  -> app.ingestion.orchestrator.IngestionOrchestrator
```

## Chat And Traces

```text
ChatService raw SSE strings
  -> app.api.v1.endpoints.chat.serialize_sse_events()
  -> app.services.chat_service.ChatStreamEvent

Trace route store calls and response mapping
  -> app.services.trace_service.TraceService
```

## External Integrations

```text
app.db.connection
  -> app.integrations.database.connection

app.db.migrations
  -> app.integrations.database.migrations

app.embeddings.local_sentence_transformer
  -> app.integrations.embeddings.sentence_transformer

app.llm.ollama_client
  -> app.integrations.llm.ollama

app.core.observability
  -> app.observability.metrics
```

The old import paths have been removed after callers were migrated.

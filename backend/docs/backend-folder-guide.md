# Backend Folder Guide

## `app/api`

Owns HTTP concerns: route functions, dependency adapters, exception mapping,
middleware, and SSE wire formatting. Endpoint files should stay thin and call
services for workflow logic.

Do not put SQL, document parsing, embedding generation, prompt construction, or
raw Ollama calls here.

## `app/services`

Coordinates complete user actions. Current services include:

```text
AdminService
DocumentService
IngestionService
SearchService
TraceService
```

Services may call repositories, RAG components, ingestion components, and
integration-friendly facades. They should not know about FastAPI response
classes except where existing schema-returning compatibility is intentionally
preserved.

## `app/repositories`

Contains persistence-facing application adapters. `DocumentRepository` currently
wraps `PgVectorChunkIndex` to preserve existing index behavior while giving
document routes and services a clearer dependency.

Future repository extraction should move chat, job, trace, chunk, and search
persistence behind similar boundaries before removing compatibility facades.

## `app/integrations`

Contains adapters for external technologies:

```text
database/connection.py
database/migrations.py
embeddings/sentence_transformer.py
llm/ollama.py
search/pgvector_search.py
search/lexical_search.py
search/hybrid_search.py
```

Legacy compatibility folders such as `app.db`, `app.embeddings`, `app.llm`,
`app.indexing`, and `app.search` have been removed. Import these capabilities
from `app.integrations`, `app.repositories`, `app.rag`, or `app.services`.

## `app/rag`

Owns RAG internals:

```text
context_builder.py
prompt_builder.py
answer_generator.py
citation_validator.py
answerer.py
traces.py
```

`RagAnswerer` remains the public facade used by current services and tests.

## `app/ingestion`

Owns ingestion pipeline behavior: parsers, validators, normalizers, chunking,
job persistence/execution, and pipeline testing. Upload-file HTTP handling is
now coordinated by `IngestionService` so routes do not own validation and job
planning rules.

## `app/bootstrap`

Creates and wires shared dependencies through `ApplicationContainer`. API
dependencies delegate to this container while preserving FastAPI dependency
override points for tests.

## `app/core`

Contains typed configuration, environment loading, constants, and shared
exception classes. New runtime environment reads should go through
`app.core.config.get_settings()`.

## `app/observability`

Contains operation metrics primitives. Request middleware and parser factory
metrics use this package.

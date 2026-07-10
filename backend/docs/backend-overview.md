# Backend Overview

The backend is now organized as a modular monolith. Runtime behavior and public
API contracts remain rooted at the existing paths; the Vite frontend can keep
using `/api/*` through its proxy.

## Request Flow

```text
Frontend
  -> API route
  -> service
  -> RAG, ingestion, repository, or integration component
  -> PostgreSQL, pgvector, Ollama, sentence-transformers, or local storage
```

## Main Responsibilities

```text
app/api
  FastAPI routes, dependencies, exception handlers, middleware, and SSE
  serialization.

app/schemas
  Pydantic request and response contracts.

app/services
  User-action coordination for documents, admin actions, ingestion jobs, search,
  and trace inspection.

app/rag
  Context construction, prompt construction, answer generation, citation
  extraction, and the compatibility answerer facade.

app/ingestion
  File validation, parser selection, normalization, parent-child chunking,
  pipeline testing, and job execution.

app/repositories
  Application-friendly persistence adapters. The document repository currently
  wraps the pgvector index compatibility facade.

app/integrations
  External technology adapters for PostgreSQL, pgvector search, lexical search,
  hybrid ranking, sentence-transformers, and Ollama.

app/core
  Shared settings, constants, environment loading, and exception types.

app/observability
  In-process operation metrics. `app.core.observability` remains a compatibility
  import path.

app/bootstrap
  Application dependency container and shared object construction.
```

## Startup

`app.main.create_app()` loads environment values, creates the FastAPI app,
registers middleware and exception handlers, includes the router, and attaches
the application container through `app.lifespan.lifespan`.

The container lazily builds shared runtime objects so the embedding model and
LLM client are not repeatedly constructed by route handlers.

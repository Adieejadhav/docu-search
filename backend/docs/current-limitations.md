# Current Limitations

## Background Execution

`INGESTION_RUN_MODE=background` uses FastAPI `BackgroundTasks` in the API
process. This is process-local and is not durable across process exits or
deploy restarts.

There is no external queue such as Redis, RabbitMQ, or SQS.

## Authentication

Admin routes are intentionally open in the current local/Docker setup. The
backend does not implement users, JWT auth, RBAC, permissions, or multitenancy.

## Storage

Uploaded files and source-file access use local filesystem paths. Object storage
is not implemented.

## Ollama

Ollama is required for answer generation and chat streaming. Startup does not
call Ollama, so the API can start while the LLM service is unavailable.

The Docker Compose setup expects Ollama as an external service by default,
usually on the host at `http://host.docker.internal:11434`.

## Embeddings

The sentence-transformers provider loads lazily and is cached per process by the
application container. Model loading is not shared across multiple OS processes.

## Database

Container-managed repositories share an in-process `DatabasePool`. The pool is
not a distributed pool and does not replace PostgreSQL server-side connection
limits. Historical migrations remain unchanged.

## Tenancy

The current schema and API are single-tenant.

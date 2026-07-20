# Current Limitations

## Background Execution

API-triggered ingestion currently uses FastAPI `BackgroundTasks` in background
mode. This is convenient for local use but is not durable across process exits or
deploy restarts. The worker entry point uses the same ingestion job service, but
there is not yet an external durable queue such as Redis, RabbitMQ, or SQS.

## Authentication

Admin routes use the existing admin-token behavior. If no admin token is
configured, admin endpoints remain open for development compatibility. The
backend does not implement user accounts, JWT authentication, role-based access
control, or multitenancy.

## Storage

Uploaded files and source-file access depend on local filesystem paths. A
distributed object store integration is not implemented.

## Ollama Availability

Ollama is required for answer generation and chat streaming, but the application
does not require Ollama to be available at web startup. Search and ingestion can
still run when LLM generation is unavailable.

## Embedding Model Lifecycle

The sentence-transformers model is loaded lazily and cached inside the process.
This avoids repeated model loads in one process, but it is still a single-process
model cache and is not coordinated across multiple workers.

## Search Repository Split

Vector search, lexical search, and hybrid ranking are extracted under
`app.integrations.search`. `PgVectorChunkIndex` still owns schema creation,
document persistence, chunk persistence, index metadata, statistics, and cleanup
SQL. A full split into dedicated chunk and index repositories remains a future
phase and should be protected by characterization tests before moving SQL.

## Database Connections

Repository and store methods still open psycopg connections per operation
through `app.integrations.database.connect_postgres`. A shared connection pool
has not yet been introduced.

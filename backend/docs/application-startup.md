# Application Startup

`app.main.create_app()` performs the FastAPI setup:

```text
load typed settings
configure logging
create FastAPI app with lifespan
register request context and rate-limit middleware
register CORS
register exception handlers
include API routers
```

`app.lifespan.lifespan()` attaches the shared `ApplicationContainer` to
`app.state.container`. The container is lazy: PostgreSQL connections are opened
by repository/store methods when work is executed, and the local embedding model
is loaded lazily by the sentence-transformers integration. This keeps import and
test startup fast and avoids loading model weights for routes that do not need
embedding.

Current startup does not eagerly fail when Ollama is unavailable. Search,
document listing, ingestion, and administrative reads can still be useful when
generation is degraded.

Database schema creation and metadata validation are currently performed by
`PgVectorChunkIndex.initialize()` when index operations run. Migration execution
remains available through the migration script instead of being forced during
web startup.

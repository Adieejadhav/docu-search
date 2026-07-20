# Dependency Flow

Runtime dependency construction has one composition root:

```text
.env / process environment
  -> app.core.config.get_settings()
  -> app.bootstrap.container.ApplicationContainer
  -> app.api.dependencies
  -> FastAPI routes
```

`app.core.config` owns environment loading and typed settings. `app.core.env`
is only a compatibility wrapper for older imports.

`ApplicationContainer` lazily owns shared application objects:

```text
settings
embedding_provider
llm_client
chunk_index
ingestion_orchestrator
ingestion_job_store
ingestion_job_service
pipeline_node_tester
rag_answerer
rag_trace_store
chat_store
document_repository
search_service
chat_service
document_service
ingestion_service
trace_service
admin_service
admin_overview_service
health_service
```

`app.api.dependencies` retrieves those objects for FastAPI. In normal runtime,
service dependencies return the exact container-owned service instances. For
tests, the dependency module still supports FastAPI overrides of lower-level
objects such as `get_chunk_index()` or `get_rag_answerer()` and composes a
temporary service around the overridden object.

Routes should depend on one service for each user-facing action. They should not
instantiate repositories, embedding providers, LLM clients, or RAG components.

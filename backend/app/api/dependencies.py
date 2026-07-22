"""
File: backend/app/api/dependencies.py
Purpose: Exposes FastAPI dependency factories backed by the application container.
"""

from __future__ import annotations

from fastapi import Depends

from app.bootstrap import (
    ApplicationContainer,
    get_application_container as get_bootstrap_application_container,
)
from app.core.config import AppSettings
from app.core.exceptions import RetrievalError
from app.integrations.embeddings import (
    EmbeddingProvider,
    LocalSentenceTransformerEmbeddingProvider,
)
from app.integrations.llm import OllamaChatClient
from app.ingestion import IngestionOrchestrator
from app.ingestion.jobs import IngestionJobService
from app.ingestion.pipeline_testing import PipelineNodeTester
from app.rag import RagAnswerer
from app.repositories import PgVectorChunkIndex
from app.repositories.chat_repository import ChatStore
from app.repositories.document_repository import DocumentRepository
from app.repositories.trace_repository import TraceRepository
from app.services import (
    AdminOverviewService,
    AdminService,
    ChatService,
    DocumentService,
    HealthService,
    IngestionService,
    SearchService,
    TraceService,
)
from app.workers import LocalTaskExecutor, TaskExecutor, WorkerTaskExecutor


def get_application_container() -> ApplicationContainer:
    return get_bootstrap_application_container()


def get_settings() -> AppSettings:
    return get_application_container().settings


def get_database_url() -> str:
    database_url = get_settings().database.url
    if not database_url:
        raise RetrievalError(
            "DATABASE_URL is required",
            code="DATABASE_URL_MISSING",
        )
    return database_url


def get_embedding_provider() -> LocalSentenceTransformerEmbeddingProvider:
    return get_application_container().embedding_provider


def get_llm_client() -> OllamaChatClient:
    return get_application_container().llm_client


def get_chunk_index() -> PgVectorChunkIndex:
    return get_application_container().chunk_index


def get_ingestion_orchestrator() -> IngestionOrchestrator:
    return get_application_container().ingestion_orchestrator


def get_ingestion_job_service() -> IngestionJobService:
    return get_application_container().ingestion_job_service


def get_pipeline_node_tester() -> PipelineNodeTester:
    return get_application_container().pipeline_node_tester


def get_rag_answerer() -> RagAnswerer:
    return get_application_container().rag_answerer


def get_rag_trace_store() -> TraceRepository:
    return get_application_container().rag_trace_store


def get_chat_store() -> ChatStore:
    return get_application_container().chat_store


def get_search_service(
    index: PgVectorChunkIndex = Depends(get_chunk_index),
    answerer: RagAnswerer = Depends(get_rag_answerer),
    trace_store: TraceRepository = Depends(get_rag_trace_store),
    container: ApplicationContainer = Depends(get_application_container),
) -> SearchService:
    if (
        _cached(container, "chunk_index") is index
        and _cached(container, "rag_answerer") is answerer
        and _cached(container, "rag_trace_store") is trace_store
    ):
        return container.search_service
    return SearchService(index=index, answerer=answerer, trace_store=trace_store)


def get_chat_service(
    store: ChatStore = Depends(get_chat_store),
    index: PgVectorChunkIndex = Depends(get_chunk_index),
    answerer: RagAnswerer = Depends(get_rag_answerer),
    trace_store: TraceRepository = Depends(get_rag_trace_store),
    container: ApplicationContainer = Depends(get_application_container),
) -> ChatService:
    if (
        _cached(container, "chat_store") is store
        and _cached(container, "chunk_index") is index
        and _cached(container, "rag_answerer") is answerer
        and _cached(container, "rag_trace_store") is trace_store
    ):
        return container.chat_service
    return ChatService(
        store=store,
        index=index,
        answerer=answerer,
        trace_store=trace_store,
    )


def get_document_service(
    index: PgVectorChunkIndex = Depends(get_chunk_index),
    container: ApplicationContainer = Depends(get_application_container),
) -> DocumentService:
    if _cached(container, "chunk_index") is index:
        return container.document_service
    return DocumentService(repository=DocumentRepository(index=index))


def get_ingestion_service(
    job_service: IngestionJobService = Depends(get_ingestion_job_service),
    container: ApplicationContainer = Depends(get_application_container),
) -> IngestionService:
    if _cached(container, "ingestion_job_service") is job_service:
        return container.ingestion_service
    return IngestionService(
        job_service=job_service,
        settings=container.settings.ingestion,
    )


def get_task_executor(
    service: IngestionService = Depends(get_ingestion_service),
    container: ApplicationContainer = Depends(get_application_container),
) -> TaskExecutor:
    if _cached(container, "ingestion_service") is service:
        return container.task_executor
    mode = container.settings.ingestion.run_mode.strip().lower()
    if mode == "background":
        return LocalTaskExecutor(ingestion_service=service)
    return WorkerTaskExecutor()


def get_trace_service(
    store: TraceRepository = Depends(get_rag_trace_store),
    container: ApplicationContainer = Depends(get_application_container),
) -> TraceService:
    if _cached(container, "rag_trace_store") is store:
        return container.trace_service
    return TraceService(store=store)


def get_admin_service(
    index: PgVectorChunkIndex = Depends(get_chunk_index),
    container: ApplicationContainer = Depends(get_application_container),
) -> AdminService:
    if _cached(container, "chunk_index") is index:
        return container.admin_service
    return AdminService(document_repository=DocumentRepository(index=index))


def get_admin_overview_service(
    database_url: str = Depends(get_database_url),
    index: PgVectorChunkIndex = Depends(get_chunk_index),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    llm_client: OllamaChatClient = Depends(get_llm_client),
    container: ApplicationContainer = Depends(get_application_container),
) -> AdminOverviewService:
    if (
        database_url == container.settings.database.url
        and _cached(container, "chunk_index") is index
        and _cached(container, "embedding_provider") is embedding_provider
        and _cached(container, "llm_client") is llm_client
    ):
        return container.admin_overview_service
    return AdminOverviewService(
        database_url=database_url,
        index=index,
        embedding_provider=embedding_provider,
        llm_client=llm_client,
    )


def get_health_service(
    database_url: str = Depends(get_database_url),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    llm_client: OllamaChatClient = Depends(get_llm_client),
    container: ApplicationContainer = Depends(get_application_container),
) -> HealthService:
    if (
        database_url == container.settings.database.url
        and _cached(container, "embedding_provider") is embedding_provider
        and _cached(container, "llm_client") is llm_client
    ):
        return container.health_service
    return HealthService(
        database_url=database_url,
        settings=container.settings,
        embedding_provider=embedding_provider,
        llm_client=llm_client,
    )


def _cached(container: ApplicationContainer, name: str) -> object | None:
    return container.__dict__.get(name)

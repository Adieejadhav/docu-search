"""
File: backend/app/bootstrap/container.py
Purpose: Builds shared application dependencies from typed settings.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property, lru_cache

from app.core.config import AppSettings, get_settings
from app.integrations.embeddings import LocalSentenceTransformerEmbeddingProvider
from app.repositories import PgVectorChunkIndex
from app.repositories.chat_repository import ChatStore
from app.repositories.document_repository import DocumentRepository
from app.ingestion import IngestionOrchestrator
from app.ingestion.jobs import IngestionJobService, IngestionJobStore
from app.ingestion.pipeline_testing import PipelineNodeTester
from app.integrations.llm import OllamaChatClient
from app.rag import RagAnswerer
from app.rag.traces import RagTraceStore
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


@dataclass
class ApplicationContainer:
    """
    Lazy dependency container for the modular monolith.

    The container can be attached during FastAPI lifespan without connecting to
    PostgreSQL or loading sentence-transformer model weights. Expensive work
    still happens lazily inside the concrete dependencies when their methods run.
    """

    settings: AppSettings

    @cached_property
    def embedding_provider(self) -> LocalSentenceTransformerEmbeddingProvider:
        settings = self.settings.embedding
        return LocalSentenceTransformerEmbeddingProvider(
            model=settings.model_name,
            dimensions=settings.dimensions,
            batch_size=settings.batch_size,
            device=settings.device,
        )

    @cached_property
    def llm_client(self) -> OllamaChatClient:
        settings = self.settings.llm
        return OllamaChatClient(
            model=settings.model_name,
            host=settings.host,
            temperature=settings.temperature,
        )

    @cached_property
    def rag_answerer(self) -> RagAnswerer:
        return RagAnswerer(llm_client=self.llm_client)

    @cached_property
    def chunk_index(self) -> PgVectorChunkIndex:
        return PgVectorChunkIndex(
            database_url=self.settings.database.url,
            embedding_provider=self.embedding_provider,
        )

    @cached_property
    def ingestion_orchestrator(self) -> IngestionOrchestrator:
        return IngestionOrchestrator(index=self.chunk_index)

    @cached_property
    def ingestion_job_store(self) -> IngestionJobStore:
        return IngestionJobStore(database_url=self.settings.database.url)

    @cached_property
    def ingestion_job_service(self) -> IngestionJobService:
        return IngestionJobService(
            store=self.ingestion_job_store,
            orchestrator=self.ingestion_orchestrator,
        )

    @cached_property
    def pipeline_node_tester(self) -> PipelineNodeTester:
        return PipelineNodeTester(
            embedding_provider=self.embedding_provider,
            index=self.chunk_index,
        )

    @cached_property
    def rag_trace_store(self) -> RagTraceStore:
        return RagTraceStore(database_url=self.settings.database.url)

    @cached_property
    def chat_store(self) -> ChatStore:
        return ChatStore(database_url=self.settings.database.url)

    @cached_property
    def document_repository(self) -> DocumentRepository:
        return DocumentRepository(index=self.chunk_index)

    @cached_property
    def search_service(self) -> SearchService:
        return SearchService(
            index=self.chunk_index,
            answerer=self.rag_answerer,
            trace_store=self.rag_trace_store,
        )

    @cached_property
    def chat_service(self) -> ChatService:
        return ChatService(
            store=self.chat_store,
            index=self.chunk_index,
            answerer=self.rag_answerer,
            trace_store=self.rag_trace_store,
        )

    @cached_property
    def document_service(self) -> DocumentService:
        return DocumentService(repository=self.document_repository)

    @cached_property
    def ingestion_service(self) -> IngestionService:
        return IngestionService(
            job_service=self.ingestion_job_service,
            settings=self.settings.ingestion,
        )

    @cached_property
    def trace_service(self) -> TraceService:
        return TraceService(store=self.rag_trace_store)

    @cached_property
    def admin_service(self) -> AdminService:
        return AdminService(document_repository=self.document_repository)

    @cached_property
    def admin_overview_service(self) -> AdminOverviewService:
        return AdminOverviewService(
            database_url=self._required_database_url(),
            index=self.chunk_index,
            embedding_provider=self.embedding_provider,
            llm_client=self.llm_client,
        )

    @cached_property
    def health_service(self) -> HealthService:
        return HealthService(
            database_url=self._required_database_url(),
            settings=self.settings,
            embedding_provider=self.embedding_provider,
            llm_client=self.llm_client,
        )

    def _required_database_url(self) -> str:
        database_url = self.settings.database.url
        if database_url is None:
            from app.core.exceptions import RetrievalError

            raise RetrievalError(
                "DATABASE_URL is required",
                code="DATABASE_URL_MISSING",
            )
        return database_url


@lru_cache(maxsize=1)
def get_application_container() -> ApplicationContainer:
    return ApplicationContainer(settings=get_settings())


def reset_application_container() -> None:
    get_application_container.cache_clear()

"""
File: backend/app/bootstrap/container.py
Purpose: Builds shared application dependencies from typed settings.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property, lru_cache

from app.core.config import AppSettings, get_settings
from app.integrations.database import DatabasePool
from app.integrations.embeddings import LocalSentenceTransformerEmbeddingProvider
from app.repositories import PgVectorChunkIndex
from app.repositories.chat_repository import ChatStore
from app.repositories.document_repository import DocumentRepository
from app.repositories.job_repository import JobRepository
from app.repositories.trace_repository import TraceRepository
from app.ingestion import IngestionOrchestrator
from app.ingestion.jobs import IngestionJobService
from app.ingestion.pipeline_testing import PipelineNodeTester
from app.integrations.llm import OllamaChatClient
from app.rag import RagAnswerer
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
    def database_pool(self) -> DatabasePool:
        return DatabasePool(database_url=self._required_database_url())

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
            database_pool=self.database_pool,
        )

    @cached_property
    def ingestion_orchestrator(self) -> IngestionOrchestrator:
        return IngestionOrchestrator(index=self.chunk_index)

    @cached_property
    def ingestion_job_store(self) -> JobRepository:
        return JobRepository(
            database_url=self.settings.database.url,
            database_pool=self.database_pool,
        )

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
    def rag_trace_store(self) -> TraceRepository:
        return TraceRepository(
            database_url=self.settings.database.url,
            database_pool=self.database_pool,
        )

    @cached_property
    def chat_store(self) -> ChatStore:
        return ChatStore(
            database_url=self.settings.database.url,
            database_pool=self.database_pool,
        )

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
    def task_executor(self) -> TaskExecutor:
        mode = self.settings.ingestion.run_mode.strip().lower()
        if mode == "background":
            return LocalTaskExecutor(ingestion_service=self.ingestion_service)
        return WorkerTaskExecutor()

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
            database_pool=self.database_pool,
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

    def close(self) -> None:
        database_pool = self.__dict__.get("database_pool")
        if database_pool is not None:
            database_pool.close()


@lru_cache(maxsize=1)
def get_application_container() -> ApplicationContainer:
    return ApplicationContainer(settings=get_settings())


def reset_application_container() -> None:
    get_application_container.cache_clear()

"""
File: backend/app/bootstrap/container.py
Purpose: Builds shared application dependencies from typed settings.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property, lru_cache

from app.repositories.chat_repository import ChatStore
from app.core.config import AppSettings, get_settings
from app.integrations.embeddings import LocalSentenceTransformerEmbeddingProvider
from app.repositories import PgVectorChunkIndex
from app.ingestion import IngestionOrchestrator
from app.ingestion.jobs import IngestionJobService
from app.ingestion.pipeline_testing import PipelineNodeTester
from app.integrations.llm import OllamaChatClient
from app.rag import RagAnswerer
from app.rag.traces import RagTraceStore


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
    def ingestion_job_service(self) -> IngestionJobService:
        return IngestionJobService(orchestrator=self.ingestion_orchestrator)

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


@lru_cache(maxsize=1)
def get_application_container() -> ApplicationContainer:
    return ApplicationContainer(settings=get_settings())


def reset_application_container() -> None:
    get_application_container.cache_clear()

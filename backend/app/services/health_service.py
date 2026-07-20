from __future__ import annotations

from collections.abc import Callable

from app.core.config import AppSettings
from app.integrations.database import DatabaseHealth, check_database_health
from app.integrations.embeddings import EmbeddingProvider
from app.integrations.llm import OllamaChatClient
from app.schemas import HealthResponse, HealthServiceStatus

DatabaseHealthChecker = Callable[[str], DatabaseHealth]


class HealthService:
    """
    Coordinates application health checks without exposing integrations to routes.
    """

    def __init__(
        self,
        *,
        database_url: str,
        settings: AppSettings,
        embedding_provider: EmbeddingProvider,
        llm_client: OllamaChatClient,
        database_health_checker: DatabaseHealthChecker = check_database_health,
    ) -> None:
        self.database_url = database_url
        self.settings = settings
        self.embedding_provider = embedding_provider
        self.llm_client = llm_client
        self.database_health_checker = database_health_checker

    def check(self) -> HealthResponse:
        database_health = self.database_health_checker(self.database_url)
        database = HealthServiceStatus(
            status="ok" if database_health.ok else "degraded",
            details=database_health.details,
        )
        embedding = HealthServiceStatus(
            status="ok",
            details={
                "provider": self.embedding_provider.name,
                "model": self.embedding_provider.model,
                "dimensions": self.embedding_provider.dimensions,
                "device": self.settings.embedding.device or "auto",
            },
        )
        llm = HealthServiceStatus(
            status="ok",
            details={
                "provider": "ollama",
                "model": self.llm_client.model,
                "host": self.llm_client.host,
            },
        )
        return HealthResponse(
            status="ok" if database.status == "ok" else "degraded",
            service="docu-search-backend",
            database=database,
            embedding=embedding,
            llm=llm,
        )

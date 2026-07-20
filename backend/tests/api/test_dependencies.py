from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api import dependencies
from app.bootstrap import ApplicationContainer
from app.core.config import (
    ApiSettings,
    AppSettings,
    DatabaseSettings,
    EmbeddingSettings,
    IngestionSettings,
    LlmSettings,
    SearchSettings,
)
from app.services import DocumentService


def test_low_level_dependency_factories_return_container_objects(monkeypatch):
    container = ApplicationContainer(settings=_settings())
    monkeypatch.setattr(
        dependencies,
        "get_bootstrap_application_container",
        lambda: container,
    )

    assert dependencies.get_application_container() is container
    assert dependencies.get_settings() is container.settings
    assert dependencies.get_database_url() == container.settings.database.url
    assert dependencies.get_embedding_provider() is container.embedding_provider
    assert dependencies.get_llm_client() is container.llm_client
    assert dependencies.get_chunk_index() is container.chunk_index
    assert dependencies.get_ingestion_orchestrator() is container.ingestion_orchestrator
    assert dependencies.get_ingestion_job_service() is container.ingestion_job_service
    assert dependencies.get_pipeline_node_tester() is container.pipeline_node_tester
    assert dependencies.get_rag_answerer() is container.rag_answerer
    assert dependencies.get_rag_trace_store() is container.rag_trace_store
    assert dependencies.get_chat_store() is container.chat_store


def test_service_dependency_factories_return_container_services(monkeypatch):
    container = ApplicationContainer(settings=_settings())
    monkeypatch.setattr(
        dependencies,
        "get_bootstrap_application_container",
        lambda: container,
    )
    app = FastAPI()

    @app.get("/identity")
    def identity(
        search=Depends(dependencies.get_search_service),
        chat=Depends(dependencies.get_chat_service),
        document=Depends(dependencies.get_document_service),
        ingestion=Depends(dependencies.get_ingestion_service),
        trace=Depends(dependencies.get_trace_service),
        admin=Depends(dependencies.get_admin_service),
        overview=Depends(dependencies.get_admin_overview_service),
        health=Depends(dependencies.get_health_service),
    ) -> dict[str, bool]:
        return {
            "search": search is container.search_service,
            "chat": chat is container.chat_service,
            "document": document is container.document_service,
            "ingestion": ingestion is container.ingestion_service,
            "trace": trace is container.trace_service,
            "admin": admin is container.admin_service,
            "overview": overview is container.admin_overview_service,
            "health": health is container.health_service,
        }

    response = TestClient(app).get("/identity")

    assert response.status_code == 200
    assert all(response.json().values())


def test_lower_level_overrides_can_still_compose_test_services(monkeypatch):
    container = ApplicationContainer(settings=_settings())
    fake_index = object()
    monkeypatch.setattr(
        dependencies,
        "get_bootstrap_application_container",
        lambda: container,
    )
    app = FastAPI()
    app.dependency_overrides[dependencies.get_chunk_index] = lambda: fake_index

    @app.get("/document-service")
    def document_service(
        service: DocumentService = Depends(dependencies.get_document_service),
    ) -> dict[str, bool]:
        return {
            "uses_override": service.repository.index is fake_index,
            "is_not_container_service": service is not container.document_service,
        }

    response = TestClient(app).get("/document-service")

    assert response.status_code == 200
    assert response.json() == {
        "uses_override": True,
        "is_not_container_service": True,
    }


def _settings() -> AppSettings:
    return AppSettings(
        database=DatabaseSettings(url="postgresql://example/db"),
        embedding=EmbeddingSettings(
            model_name="fake-embedding",
            dimensions=3,
            batch_size=2,
        ),
        llm=LlmSettings(
            host="http://ollama.example",
            model_name="fake-llm",
            temperature=0,
        ),
        search=SearchSettings(),
        ingestion=IngestionSettings(),
        api=ApiSettings(),
    )

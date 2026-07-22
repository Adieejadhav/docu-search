from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.lifespan as lifespan_module
from app.core.config import (
    ApiSettings,
    AppSettings,
    DatabaseSettings,
    EmbeddingSettings,
    IngestionSettings,
    LlmSettings,
    SearchSettings,
)


def test_lifespan_attaches_and_closes_container(monkeypatch):
    container = _FakeContainer()
    monkeypatch.setattr(
        lifespan_module,
        "get_application_container",
        lambda: container,
    )
    app = FastAPI(lifespan=lifespan_module.lifespan)

    with TestClient(app):
        assert app.state.container is container
        assert app.state.startup_checks[0].name == "ingestion_run_mode"

    assert container.closed is True


class _FakeContainer:
    def __init__(self) -> None:
        self.closed = False
        self.settings = AppSettings(
            database=DatabaseSettings(url=None),
            embedding=EmbeddingSettings(),
            llm=LlmSettings(),
            search=SearchSettings(),
            ingestion=IngestionSettings(run_mode="background"),
            api=ApiSettings(),
        )

    def close(self) -> None:
        self.closed = True

from __future__ import annotations

import os

from fastapi import APIRouter, Depends

from app.api.dependencies import get_database_url, get_embedding_provider, get_llm_client
from app.db import check_database_health
from app.schemas import HealthResponse, HealthServiceStatus

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check(database_url: str = Depends(get_database_url)) -> HealthResponse:
    database_health = check_database_health(database_url)
    embedding_provider = get_embedding_provider()
    llm_client = get_llm_client()

    database = HealthServiceStatus(
        status="ok" if database_health.ok else "degraded",
        details=database_health.details,
    )
    embedding = HealthServiceStatus(
        status="ok",
        details={
            "provider": embedding_provider.name,
            "model": embedding_provider.model,
            "dimensions": embedding_provider.dimensions,
            "device": os.getenv("LOCAL_EMBEDDING_DEVICE") or "auto",
        },
    )
    llm = HealthServiceStatus(
        status="ok",
        details={
            "provider": "ollama",
            "model": llm_client.model,
            "host": llm_client.host,
        },
    )
    return HealthResponse(
        status="ok" if database.status == "ok" else "degraded",
        service="docu-search-backend",
        database=database,
        embedding=embedding,
        llm=llm,
    )

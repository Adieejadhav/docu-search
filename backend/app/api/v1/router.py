from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    chat,
    documents,
    health,
    ingestion,
    pipeline,
    search,
    traces,
)

v1_router = APIRouter()

v1_router.include_router(
    health.router,
    tags=["health"],
)

v1_router.include_router(
    documents.router,
    prefix="/documents",
    tags=["documents"],
)

v1_router.include_router(
    chat.router,
    prefix="/chat",
    tags=["chat"],
)

v1_router.include_router(
    search.router,
    tags=["search"],
)

v1_router.include_router(
    admin.router,
    prefix="/admin",
    tags=["admin"],
)
v1_router.include_router(
    documents.admin_router,
    prefix="/admin/documents",
    tags=["admin", "documents"],
)
v1_router.include_router(
    ingestion.router,
    prefix="/admin/ingestion",
    tags=["admin", "ingestion"],
)
v1_router.include_router(
    pipeline.router,
    prefix="/admin/pipeline",
    tags=["admin", "pipeline"],
)
v1_router.include_router(
    traces.router,
    prefix="/admin/traces",
    tags=["admin", "traces"],
)

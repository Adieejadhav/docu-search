from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import require_admin
from app.api.routes import (
    admin,
    chat,
    documents,
    evaluation,
    health,
    ingestion,
    pipeline,
    search,
    traces,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(search.router, tags=["search"])
api_router.include_router(
    admin.router,
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)
api_router.include_router(
    documents.admin_router,
    prefix="/admin/documents",
    tags=["admin", "documents"],
    dependencies=[Depends(require_admin)],
)
api_router.include_router(
    ingestion.router,
    prefix="/admin/ingestion",
    tags=["admin", "ingestion"],
    dependencies=[Depends(require_admin)],
)
api_router.include_router(
    evaluation.router,
    prefix="/admin/evaluation",
    tags=["admin", "evaluation"],
    dependencies=[Depends(require_admin)],
)
api_router.include_router(
    pipeline.router,
    prefix="/admin/pipeline",
    tags=["admin", "pipeline"],
    dependencies=[Depends(require_admin)],
)
api_router.include_router(
    traces.router,
    prefix="/admin/traces",
    tags=["admin", "traces"],
    dependencies=[Depends(require_admin)],
)

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import admin, documents, health, search

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(search.router, tags=["search"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])

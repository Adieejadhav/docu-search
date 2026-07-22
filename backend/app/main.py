"""
File: backend/app/main.py
Purpose: FastAPI application entrypoint for Docu Search.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.api.exception_handlers import app_error_handler
from app.api.middleware import InMemoryRateLimitMiddleware, RequestContextMiddleware
from app.core.config import AppSettings, get_settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging
from app.lifespan import lifespan


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)
    app = FastAPI(
        title="Docu Search API",
        version="0.1.0",
        description="Document ingestion, retrieval, and grounded RAG answer API.",
        lifespan=lifespan,
    )
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(InMemoryRateLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins(settings),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(AppError, app_error_handler)
    app.include_router(api_router)

    @app.get("/")
    def root() -> dict[str, str]:
        return {
            "service": "docu-search-backend",
            "status": "ok",
        }

    return app

def cors_origins(settings: AppSettings | None = None) -> list[str]:
    settings = settings or get_settings()
    return list(settings.api.cors_origins)


app = create_app()

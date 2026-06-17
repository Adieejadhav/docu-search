"""
File: backend/app/main.py
Purpose: FastAPI application entrypoint for Docu Search.
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.api.errors import app_error_handler
from app.core.env import load_environment
from app.core.exceptions import AppError


def create_app() -> FastAPI:
    load_environment()
    app = FastAPI(
        title="Docu Search API",
        version="0.1.0",
        description="Document ingestion, retrieval, and grounded RAG answer API.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins(),
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


def cors_origins() -> list[str]:
    raw_origins = os.getenv(
        "API_CORS_ORIGINS",
        ",".join(
            [
                "http://127.0.0.1:5173",
                "http://localhost:5173",
                "http://127.0.0.1:5174",
                "http://localhost:5174",
            ]
        ),
    )
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]


app = create_app()

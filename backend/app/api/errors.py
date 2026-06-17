"""
File: backend/app/api/errors.py
Purpose: Maps application exceptions to consistent HTTP error responses.
"""

from __future__ import annotations

from fastapi import Request, status
from fastapi.responses import JSONResponse

from app.core.exceptions import AppError, EmbeddingError, IngestionError, LLMError, RetrievalError
from app.schemas import ApiErrorResponse


def app_error_status_code(exc: AppError) -> int:
    if isinstance(exc, IngestionError):
        return status.HTTP_400_BAD_REQUEST
    if isinstance(exc, RetrievalError):
        if exc.code in {"DATABASE_URL_MISSING", "PSYCOPG_PACKAGE_MISSING"}:
            return status.HTTP_503_SERVICE_UNAVAILABLE
        return status.HTTP_400_BAD_REQUEST
    if isinstance(exc, EmbeddingError):
        return status.HTTP_500_INTERNAL_SERVER_ERROR
    if isinstance(exc, LLMError):
        return status.HTTP_502_BAD_GATEWAY
    return status.HTTP_500_INTERNAL_SERVER_ERROR


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    payload = ApiErrorResponse(
        code=exc.code,
        message=exc.message,
        details=exc.details,
    )
    return JSONResponse(
        status_code=app_error_status_code(exc),
        content=payload.model_dump(mode="json"),
    )

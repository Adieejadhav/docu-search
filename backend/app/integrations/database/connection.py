"""
File: backend/app/integrations/database/connection.py
Purpose: Provides PostgreSQL connection helpers with bounded timeouts.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError as PydanticValidationError

from app.core.config import get_settings
from app.core.exceptions import RetrievalError


DEFAULT_DATABASE_CONNECT_TIMEOUT_SECONDS = 2


def connect_postgres(
    database_url: str,
    *,
    package_error_message: str = "The psycopg[binary] package is required for database access",
    package_error_code: str = "PSYCOPG_PACKAGE_MISSING",
) -> Any:
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RetrievalError(
            package_error_message,
            code=package_error_code,
        ) from exc

    connect_timeout = database_connect_timeout_seconds()
    try:
        return psycopg.connect(
            database_url,
            row_factory=dict_row,
            connect_timeout=connect_timeout,
        )
    except psycopg.OperationalError as exc:
        raise RetrievalError(
            "Could not connect to PostgreSQL",
            code="DATABASE_CONNECTION_FAILED",
            details={
                "connect_timeout_seconds": connect_timeout,
                "message": str(exc),
            },
        ) from exc


def database_connect_timeout_seconds() -> int:
    try:
        timeout = get_settings().database.connect_timeout_seconds
    except (ValueError, PydanticValidationError) as exc:
        raise RetrievalError(
            "DATABASE_CONNECT_TIMEOUT_SECONDS must be an integer",
            code="INVALID_DATABASE_CONNECT_TIMEOUT_SECONDS",
        ) from exc

    if timeout < 1:
        raise RetrievalError(
            "DATABASE_CONNECT_TIMEOUT_SECONDS must be greater than zero",
            code="INVALID_DATABASE_CONNECT_TIMEOUT_SECONDS",
            details={"value": str(timeout)},
        )

    return timeout

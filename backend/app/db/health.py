"""
File: backend/app/db/health.py
Purpose: Provides non-mutating PostgreSQL/pgvector health checks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.exceptions import AppError
from app.db.connection import connect_postgres


@dataclass(frozen=True)
class DatabaseHealth:
    ok: bool
    details: dict[str, Any] = field(default_factory=dict)


def check_database_health(database_url: str) -> DatabaseHealth:
    try:
        with connect_postgres(
            database_url,
            package_error_message=(
                "The psycopg[binary] package is required for database health checks"
            ),
        ) as connection:
            ping = connection.execute("SELECT 1 AS ok").fetchone()
            extension = connection.execute(
                """
                SELECT extversion
                FROM pg_extension
                WHERE extname = 'vector'
                """
            ).fetchone()
            tables = {
                table_name: connection.execute(
                    "SELECT to_regclass(%s) AS relation_name",
                    (f"public.{table_name}",),
                ).fetchone()["relation_name"]
                is not None
                for table_name in (
                    "documents",
                    "parent_chunks",
                    "child_chunks",
                    "child_embeddings",
                )
            }

        return DatabaseHealth(
            ok=bool(ping and ping["ok"] == 1 and extension),
            details={
                "pgvector_available": extension is not None,
                "pgvector_version": extension["extversion"] if extension else None,
                "tables": tables,
            },
        )
    except Exception as exc:
        if isinstance(exc, AppError):
            return DatabaseHealth(
                ok=False,
                details={
                    "error": exc.code,
                    "message": exc.message,
                    **({"details": exc.details} if exc.details else {}),
                },
            )

        return DatabaseHealth(
            ok=False,
            details={
                "error": exc.__class__.__name__,
                "message": str(exc),
            },
        )

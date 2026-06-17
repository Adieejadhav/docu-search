"""
File: backend/app/db/health.py
Purpose: Provides non-mutating PostgreSQL/pgvector health checks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DatabaseHealth:
    ok: bool
    details: dict[str, Any] = field(default_factory=dict)


def check_database_health(database_url: str) -> DatabaseHealth:
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        return DatabaseHealth(
            ok=False,
            details={
                "error": "PSYCOPG_PACKAGE_MISSING",
                "message": str(exc),
            },
        )

    try:
        with psycopg.connect(database_url, row_factory=dict_row) as connection:
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
        return DatabaseHealth(
            ok=False,
            details={
                "error": exc.__class__.__name__,
                "message": str(exc),
            },
        )

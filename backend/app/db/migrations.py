"""
File: backend/app/db/migrations.py
Purpose: Applies versioned SQL migrations to PostgreSQL.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import os
from typing import Any

from app.core.env import load_environment
from app.core.exceptions import RetrievalError
from app.db.connection import connect_postgres


@dataclass(frozen=True)
class MigrationRecord:
    version: str
    name: str
    checksum: str


@dataclass(frozen=True)
class MigrationResult:
    applied: list[MigrationRecord]
    skipped: list[MigrationRecord]


class SqlMigrationRunner:
    """
    Lightweight SQL migration runner for production and local setup.

    Migration files are applied in filename order. A checksum is stored so an
    already-applied migration cannot silently change underneath the database.
    """

    def __init__(
        self,
        *,
        database_url: str | None = None,
        migrations_dir: Path | None = None,
    ) -> None:
        load_environment()
        self.database_url = database_url or os.getenv("DATABASE_URL")
        if not self.database_url:
            raise RetrievalError(
                "DATABASE_URL is required for database migrations",
                code="DATABASE_URL_MISSING",
            )

        self.migrations_dir = migrations_dir or default_migrations_dir()

    def apply(self) -> MigrationResult:
        migration_files = self._migration_files()
        applied: list[MigrationRecord] = []
        skipped: list[MigrationRecord] = []

        with self._connect() as connection:
            self._ensure_schema_migrations(connection)
            existing = self._existing_migrations(connection)

            for migration_file in migration_files:
                record = self._record_for_file(migration_file)
                existing_checksum = existing.get(record.version)
                if existing_checksum:
                    if existing_checksum != record.checksum:
                        raise RetrievalError(
                            "Applied migration checksum does not match file",
                            code="MIGRATION_CHECKSUM_MISMATCH",
                            details={
                                "version": record.version,
                                "name": record.name,
                            },
                        )
                    skipped.append(record)
                    continue

                sql = migration_file.read_text(encoding="utf-8")
                connection.execute(sql)
                connection.execute(
                    """
                    INSERT INTO schema_migrations(version, name, checksum)
                    VALUES(%s, %s, %s)
                    """,
                    (record.version, record.name, record.checksum),
                )
                applied.append(record)

        return MigrationResult(applied=applied, skipped=skipped)

    def _migration_files(self) -> list[Path]:
        if not self.migrations_dir.exists():
            raise RetrievalError(
                "Migration directory was not found",
                code="MIGRATION_DIRECTORY_NOT_FOUND",
                details={"migrations_dir": str(self.migrations_dir)},
            )

        return sorted(self.migrations_dir.glob("*.sql"))

    def _record_for_file(self, path: Path) -> MigrationRecord:
        content = path.read_bytes()
        return MigrationRecord(
            version=path.stem.split("_", 1)[0],
            name=path.name,
            checksum=hashlib.sha256(content).hexdigest(),
        )

    def _connect(self) -> Any:
        return connect_postgres(
            self.database_url,
            package_error_message=(
                "The psycopg[binary] package is required for database migrations"
            ),
        )

    def _ensure_schema_migrations(self, connection: Any) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                checksum TEXT NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )

    def _existing_migrations(self, connection: Any) -> dict[str, str]:
        rows = connection.execute(
            "SELECT version, checksum FROM schema_migrations"
        ).fetchall()
        return {row["version"]: row["checksum"] for row in rows}


def default_migrations_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "db" / "migrations"

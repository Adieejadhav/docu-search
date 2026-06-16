from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from app.core.env import load_environment
from app.core.exceptions import RetrievalError


APP_TABLES = (
    "child_embeddings",
    "child_chunks",
    "parent_chunks",
    "documents",
)


def main(argv: list[str] | None = None) -> int:
    configure_terminal_encoding()
    load_environment()
    args = build_parser().parse_args(argv)

    try:
        if not args.yes:
            print(
                "ERROR: Refusing to clear database without --yes",
                file=sys.stderr,
            )
            return 2

        database_url = resolve_database_url(args.database_url)
        if args.reset_schema:
            reset_schema(database_url=database_url, migration_path=args.migration_sql)
        else:
            clear_index_data(database_url=database_url)

        print("DATABASE CLEAR SUMMARY")
        print(f"  database_url: {redact_database_url(database_url)}")
        print(f"  mode: {'reset_schema' if args.reset_schema else 'data_only'}")
        print("  status: completed")
        return 0
    except Exception as exc:
        print_error(exc)
        return 1


def configure_terminal_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="docu-clear-db",
        description="Clear or reset the PostgreSQL + pgvector database used by Docu Search.",
    )
    parser.add_argument("--database-url", help="PostgreSQL DATABASE_URL.")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm the destructive database clear operation.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--data-only",
        action="store_true",
        help=(
            "Clear indexed documents, parent chunks, child chunks, and embeddings. "
            "This is the default mode."
        ),
    )
    mode.add_argument(
        "--reset-schema",
        action="store_true",
        help="Drop and recreate the public schema, then reapply the pgvector migration.",
    )
    parser.add_argument(
        "--migration-sql",
        type=Path,
        default=default_migration_path(),
        help="Migration SQL file used with --reset-schema.",
    )
    return parser


def resolve_database_url(database_url: str | None) -> str:
    resolved = database_url or os.getenv("DATABASE_URL")
    if not resolved:
        raise RetrievalError(
            "DATABASE_URL is required for database clearing",
            code="DATABASE_URL_MISSING",
        )
    return resolved


def clear_index_data(*, database_url: str) -> None:
    with connect(database_url) as connection:
        ensure_tables_exist(connection)
        for table_name in APP_TABLES:
            connection.execute(f"DELETE FROM {table_name}")


def reset_schema(*, database_url: str, migration_path: Path) -> None:
    if not migration_path.is_file():
        raise RetrievalError(
            "Migration SQL file was not found",
            code="MIGRATION_SQL_NOT_FOUND",
            details={"migration_path": str(migration_path)},
        )

    migration_sql = migration_path.read_text(encoding="utf-8")
    with connect(database_url) as connection:
        connection.execute("DROP SCHEMA IF EXISTS public CASCADE")
        connection.execute("CREATE SCHEMA public")
        connection.execute("CREATE EXTENSION IF NOT EXISTS vector")
        connection.execute(migration_sql)


def ensure_tables_exist(connection) -> None:
    missing_tables: list[str] = []
    for table_name in APP_TABLES:
        row = connection.execute(
            "SELECT to_regclass(%s) AS table_name",
            (f"public.{table_name}",),
        ).fetchone()
        if row["table_name"] is None:
            missing_tables.append(table_name)

    if missing_tables:
        raise RetrievalError(
            "Cannot clear data because index tables are missing",
            code="INDEX_TABLES_MISSING",
            details={"missing_tables": missing_tables},
        )


def connect(database_url: str):
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RetrievalError(
            "The psycopg[binary] package is required for database clearing",
            code="PSYCOPG_PACKAGE_MISSING",
        ) from exc

    return psycopg.connect(database_url, row_factory=dict_row)


def default_migration_path() -> Path:
    return Path(__file__).resolve().parents[2] / "db" / "migrations" / (
        "001_pgvector_chunk_index.sql"
    )


def redact_database_url(database_url: str) -> str:
    if "@" not in database_url:
        return database_url

    scheme_and_credentials, host = database_url.split("@", 1)
    scheme = scheme_and_credentials.split("://", 1)[0]
    return f"{scheme}://***@{host}"


def print_error(exc: Exception) -> None:
    if isinstance(exc, RetrievalError):
        print(f"ERROR: {exc.code}: {exc.message}", file=sys.stderr)
        if exc.details:
            print(f"DETAILS: {exc.details}", file=sys.stderr)
        return

    print(f"ERROR: {exc}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())

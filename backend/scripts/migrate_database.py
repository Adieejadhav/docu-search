"""
File: backend/app/cli/migrate_database.py
Purpose: Applies versioned PostgreSQL schema migrations.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.core.exceptions import AppError
from app.core.logging import format_multiline_event
from app.integrations.database import SqlMigrationRunner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Apply Docu Search PostgreSQL schema migrations.",
    )
    parser.add_argument(
        "--migrations-dir",
        type=Path,
        default=None,
        help="Directory containing ordered .sql migration files.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = SqlMigrationRunner(migrations_dir=args.migrations_dir).apply()
    except AppError as exc:
        print(
            format_multiline_event(
                utc_timestamp(),
                "ERROR",
                "migration_failed",
                [
                    ("code", exc.code),
                    ("message", exc.message),
                    ("details", json.dumps(exc.details, sort_keys=True)),
                ],
            ),
            file=sys.stderr,
        )
        return 1

    print(
        format_multiline_event(
            utc_timestamp(),
            None,
            "migrations_complete",
            [
                ("applied", len(result.applied)),
                ("skipped", len(result.skipped)),
                ("applied_names", migration_names(result.applied)),
                ("skipped_names", migration_names(result.skipped)),
            ],
        ),
    )
    return 0


def migration_names(records) -> str:
    if not records:
        return "-"
    return ",".join(f"{record.version}:{record.name}" for record in records)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


if __name__ == "__main__":
    raise SystemExit(main())

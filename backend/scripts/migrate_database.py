"""
File: backend/app/cli/migrate_database.py
Purpose: Applies versioned PostgreSQL schema migrations.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.core.exceptions import AppError
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
            "level=error service=migrations event=failed"
            f" code={exc.code}"
            f" message={json.dumps(exc.message)}"
            f" details={json.dumps(exc.details, sort_keys=True)}",
            file=sys.stderr,
        )
        return 1

    print(
        "level=info service=migrations event=complete"
        f" applied_count={len(result.applied)}"
        f" skipped_count={len(result.skipped)}"
        f" applied={migration_names(result.applied)}"
        f" skipped={migration_names(result.skipped)}",
    )
    return 0


def migration_names(records) -> str:
    if not records:
        return "-"
    return ",".join(f"{record.version}:{record.name}" for record in records)


if __name__ == "__main__":
    raise SystemExit(main())

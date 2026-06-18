"""
File: backend/app/cli/migrate_database.py
Purpose: Applies versioned PostgreSQL schema migrations.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.core.exceptions import AppError
from app.db import SqlMigrationRunner


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
        print(f"ERROR: {exc.code}: {exc.message}", file=sys.stderr)
        if exc.details:
            print(f"DETAILS: {exc.details}", file=sys.stderr)
        return 1

    print("MIGRATION SUMMARY")
    print(f"  applied: {len(result.applied)}")
    print(f"  skipped: {len(result.skipped)}")
    for record in result.applied:
        print(f"  applied {record.version}: {record.name}")
    for record in result.skipped:
        print(f"  skipped {record.version}: {record.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

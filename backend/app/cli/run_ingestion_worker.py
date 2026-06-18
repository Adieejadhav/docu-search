"""
File: backend/app/cli/run_ingestion_worker.py
Purpose: Runs queued ingestion jobs from PostgreSQL.
"""

from __future__ import annotations

import argparse
import sys
from time import sleep

from app.core.exceptions import AppError
from app.ingestion.jobs import IngestionJobService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run queued Docu Search ingestion jobs.",
    )
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=3.0,
        help="Seconds to wait between queue polls.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run at most one queued job and exit.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    service = IngestionJobService()

    print("INGESTION WORKER STARTED")
    try:
        while True:
            job = service.run_next_queued_job()
            if job is None:
                if args.once:
                    print("No queued ingestion jobs.")
                    return 0
                sleep(max(args.poll_seconds, 0.2))
                continue

            print(
                "JOB COMPLETED"
                f" id={job.id}"
                f" status={job.status}"
                f" indexed_child_count={job.indexed_child_count}"
                f" failures={job.failure_count}"
            )
            if args.once:
                return 0
    except KeyboardInterrupt:
        print("INGESTION WORKER STOPPED")
        return 0
    except AppError as exc:
        print(f"ERROR: {exc.code}: {exc.message}", file=sys.stderr)
        if exc.details:
            print(f"DETAILS: {exc.details}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

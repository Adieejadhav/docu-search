"""
File: backend/app/cli/run_ingestion_worker.py
Purpose: Runs queued ingestion jobs from PostgreSQL.
"""

from __future__ import annotations

import argparse
import sys

from app.core.exceptions import AppError
from app.ingestion.jobs import IngestionJobRecord
from app.workers import IngestionWorker


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
    worker = IngestionWorker()

    print("INGESTION WORKER STARTED")
    try:
        worker.run(
            poll_seconds=args.poll_seconds,
            once=args.once,
            on_job_completed=print_job_completed,
            on_idle=lambda: print("No queued ingestion jobs.") if args.once else None,
        )
        return 0
    except KeyboardInterrupt:
        print("INGESTION WORKER STOPPED")
        return 0
    except AppError as exc:
        print(f"ERROR: {exc.code}: {exc.message}", file=sys.stderr)
        if exc.details:
            print(f"DETAILS: {exc.details}", file=sys.stderr)
        return 1


def print_job_completed(job: IngestionJobRecord) -> None:
    print(
        "JOB COMPLETED"
        f" id={job.id}"
        f" status={job.status}"
        f" indexed_child_count={job.indexed_child_count}"
        f" failures={job.failure_count}"
    )


if __name__ == "__main__":
    raise SystemExit(main())

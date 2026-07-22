"""
File: backend/app/cli/run_ingestion_worker.py
Purpose: Runs queued ingestion jobs from PostgreSQL.
"""

from __future__ import annotations

import argparse
import json
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

    print(f"level=info service=worker event=started poll_seconds={args.poll_seconds} once={args.once}")
    try:
        worker.run(
            poll_seconds=args.poll_seconds,
            once=args.once,
            on_job_completed=print_job_completed,
            on_idle=lambda: print("level=info service=worker event=idle queued_jobs=0")
            if args.once
            else None,
        )
        return 0
    except KeyboardInterrupt:
        print("level=info service=worker event=stopped reason=keyboard_interrupt")
        return 0
    except AppError as exc:
        print(
            "level=error service=worker event=failed"
            f" code={exc.code}"
            f" message={json.dumps(exc.message)}"
            f" details={json.dumps(exc.details, sort_keys=True)}",
            file=sys.stderr,
        )
        return 1


def print_job_completed(job: IngestionJobRecord) -> None:
    print(
        "level=info service=worker event=job_completed"
        f" id={job.id}"
        f" status={job.status}"
        f" indexed_child_count={job.indexed_child_count}"
        f" failures={job.failure_count}"
    )


if __name__ == "__main__":
    raise SystemExit(main())

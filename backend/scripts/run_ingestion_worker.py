"""
File: backend/app/cli/run_ingestion_worker.py
Purpose: Runs queued ingestion jobs from PostgreSQL.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from app.core.exceptions import AppError
from app.core.logging import format_multiline_event
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

    print(
        format_multiline_event(
            utc_timestamp(),
            None,
            "ingestion_worker_started",
            [
                ("poll", f"{args.poll_seconds}s"),
                ("once", args.once),
            ],
        )
    )
    try:
        worker.run(
            poll_seconds=args.poll_seconds,
            once=args.once,
            on_job_completed=print_job_completed,
            on_idle=lambda: print(
                format_multiline_event(
                    utc_timestamp(),
                    None,
                    "ingestion_worker_idle",
                    [("queued", 0)],
                )
            )
            if args.once
            else None,
        )
        return 0
    except KeyboardInterrupt:
        print(
            format_multiline_event(
                utc_timestamp(),
                None,
                "ingestion_worker_stopped",
                [("reason", "keyboard_interrupt")],
            )
        )
        return 0
    except AppError as exc:
        print(
            format_multiline_event(
                utc_timestamp(),
                "ERROR",
                "ingestion_worker_failed",
                [
                    ("code", exc.code),
                    ("message", exc.message),
                    ("details", json.dumps(exc.details, sort_keys=True)),
                ],
            ),
            file=sys.stderr,
        )
        return 1


def print_job_completed(job: IngestionJobRecord) -> None:
    print(
        format_multiline_event(
            utc_timestamp(),
            None,
            "ingestion_job_completed",
            [
                ("id", job.id),
                ("status", job.status),
                ("indexed", job.indexed_child_count),
                ("failures", job.failure_count),
            ],
        )
    )


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

from dataclasses import asdict

from app.observability import DEFAULT_OPERATION_METRICS_RECORDER


def metrics_snapshot() -> dict:
    return asdict(DEFAULT_OPERATION_METRICS_RECORDER.snapshot())

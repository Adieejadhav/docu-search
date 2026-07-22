"""
File: backend/app/bootstrap/startup_checks.py
Purpose: Runs lightweight startup checks without initializing heavy integrations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.config import AppSettings
from app.core.exceptions import IngestionError


@dataclass(frozen=True)
class StartupCheckResult:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)


def run_startup_checks(settings: AppSettings) -> list[StartupCheckResult]:
    results = [
        check_ingestion_run_mode(settings),
        check_database_url_configured(settings),
    ]
    failures = [result for result in results if result.status == "failed"]
    if failures:
        raise IngestionError(
            "Startup checks failed",
            code="STARTUP_CHECK_FAILED",
            details={
                "checks": [
                    {
                        "name": result.name,
                        "status": result.status,
                        "details": result.details,
                    }
                    for result in failures
                ]
            },
        )
    return results


def check_ingestion_run_mode(settings: AppSettings) -> StartupCheckResult:
    mode = settings.ingestion.run_mode.strip().lower()
    if mode not in {"background", "worker"}:
        return StartupCheckResult(
            name="ingestion_run_mode",
            status="failed",
            details={"run_mode": mode},
        )
    return StartupCheckResult(
        name="ingestion_run_mode",
        status="ok",
        details={"run_mode": mode},
    )


def check_database_url_configured(settings: AppSettings) -> StartupCheckResult:
    if settings.database.url:
        return StartupCheckResult(name="database_url", status="ok")
    return StartupCheckResult(
        name="database_url",
        status="skipped",
        details={"reason": "DATABASE_URL is not configured"},
    )

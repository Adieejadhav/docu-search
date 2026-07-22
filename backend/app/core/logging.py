"""
File: backend/app/core/logging.py
Purpose: Centralizes logging configuration for API, CLI, and worker processes.
"""

from __future__ import annotations

import logging
import time

from app.core.config import AppSettings, get_settings


class RequestAwareFormatter(logging.Formatter):
    converter = time.gmtime

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        context = []
        for name, label in (
            ("request_id", "request_id"),
            ("method", "method"),
            ("path", "path"),
            ("status_code", "status"),
            ("duration_ms", "duration_ms"),
        ):
            value = getattr(record, name, None)
            if value is not None:
                context.append(f"{label}={value}")
        if not context:
            return message
        return f"{message} {' '.join(context)}"


def configure_logging(settings: AppSettings | None = None) -> None:
    settings = settings or get_settings()
    handler = logging.StreamHandler()
    handler.setFormatter(
        RequestAwareFormatter(
            "ts=%(asctime)s level=%(levelname)s service=%(name)s event=%(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        ),
    )
    logging.basicConfig(
        level=settings.api.log_level,
        handlers=[handler],
        force=True,
    )
    logging.getLogger("uvicorn.access").disabled = True

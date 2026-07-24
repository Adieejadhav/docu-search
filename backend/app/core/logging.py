"""
File: backend/app/core/logging.py
Purpose: Centralizes logging configuration for API, CLI, and worker processes.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any
from urllib.parse import unquote, urlsplit

from app.core.config import AppSettings, get_settings


MAX_INLINE_LOG_LENGTH = 120
HTTP_REQUEST_RE = re.compile(
    r'^HTTP Request: (?P<method>[A-Z]+) (?P<url>\S+) '
    r'"HTTP/(?P<http_version>[^ ]+) (?P<status_code>\d{3}) (?P<reason>[^"]+)"$',
)


class CompactFormatter(logging.Formatter):
    converter = time.gmtime

    def format(self, record: logging.LogRecord) -> str:
        timestamp = self.formatTime(record, self.datefmt)
        if _has_request_context(record):
            return format_request_log(
                timestamp=timestamp,
                method=str(getattr(record, "method")),
                path=str(getattr(record, "path")),
                status_code=int(getattr(record, "status_code")),
                duration_ms=float(getattr(record, "duration_ms")),
                request_id=getattr(record, "request_id", None),
            )

        level = record.levelname.upper()
        message = single_line(record.getMessage())
        external_http = parse_http_request_log(message)
        if external_http is not None:
            return format_external_http_log(
                timestamp=timestamp,
                level=level,
                details=external_http,
            )

        compact = f"{timestamp} {level} {message}"
        if len(compact) <= MAX_INLINE_LOG_LENGTH:
            return compact

        fields: list[tuple[str, Any]] = []
        if record.name and record.name != "root":
            fields.append(("logger", record.name))
        fields.append(("message", message))
        return format_multiline_event(timestamp, level, "log", fields)


def configure_logging(settings: AppSettings | None = None) -> None:
    settings = settings or get_settings()
    handler = logging.StreamHandler()
    handler.setFormatter(
        CompactFormatter(
            "%(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        ),
    )
    logging.basicConfig(
        level=settings.api.log_level,
        handlers=[handler],
        force=True,
    )
    logging.captureWarnings(True)
    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    for logger_name in ("huggingface_hub", "sentence_transformers", "transformers"):
        dedupe_library_logger(logger_name)


def single_line(value: str) -> str:
    return " ".join(value.split())


def format_request_log(
    *,
    timestamp: str,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    request_id: Any = None,
) -> str:
    duration = f"{duration_ms:.1f}ms"
    message = f"{timestamp} {method} {path} {status_code} {duration}"
    if status_code >= 400 and request_id:
        message = f"{message} rid={short_request_id(request_id)}"
    if len(message) <= MAX_INLINE_LOG_LENGTH:
        return message

    fields: list[tuple[str, Any]] = [
        ("method", method),
        ("path", path),
        ("status", status_code),
        ("duration", duration),
    ]
    if status_code >= 400 and request_id:
        fields.append(("rid", short_request_id(request_id)))
    return format_multiline_event(timestamp, None, "request", fields)


def parse_http_request_log(message: str) -> dict[str, str] | None:
    match = HTTP_REQUEST_RE.match(message)
    if match is None:
        return None
    return match.groupdict()


def format_external_http_log(
    *,
    timestamp: str,
    level: str,
    details: dict[str, str],
) -> str:
    url = details["url"]
    url_parts = urlsplit(url)
    fields: list[tuple[str, Any]] = [
        ("method", details["method"]),
        ("host", url_parts.netloc or "-"),
    ]
    fields.extend(huggingface_url_fields(url_parts.path))
    if not any(key in {"model", "file", "path"} for key, _value in fields):
        fields.append(("path", unquote(url_parts.path or "/")))
    if url_parts.query:
        fields.append(("query", url_parts.query))
    fields.extend(
        [
            ("status", details["status_code"]),
            ("reason", details["reason"]),
        ]
    )
    return format_multiline_event(timestamp, level, "external_http", fields)


def huggingface_url_fields(path: str) -> list[tuple[str, str]]:
    parts = [unquote(part) for part in path.strip("/").split("/") if part]
    if len(parts) >= 7 and parts[:3] == ["api", "resolve-cache", "models"]:
        return [
            ("model", "/".join(parts[3:5])),
            ("revision", parts[5]),
            ("file", "/".join(parts[6:])),
        ]
    if len(parts) >= 5 and parts[2] == "resolve":
        return [
            ("model", "/".join(parts[:2])),
            ("revision", parts[3]),
            ("file", "/".join(parts[4:])),
        ]
    return []


def format_multiline_event(
    timestamp: str,
    level: str | None,
    event: str,
    fields: list[tuple[str, Any]],
) -> str:
    header_parts = [timestamp]
    if level:
        header_parts.append(level)
    header_parts.append(event)
    lines = [" ".join(header_parts)]
    for key, value in fields:
        lines.extend(format_field_lines(key, value))
    return "\n".join(lines)


def format_field_lines(key: str, value: Any) -> list[str]:
    normalized = single_line(str(value))
    prefix = f"  {key}="
    if len(prefix) + len(normalized) <= MAX_INLINE_LOG_LENGTH:
        return [f"{prefix}{normalized}"]

    chunks = split_long_value(
        normalized,
        width=MAX_INLINE_LOG_LENGTH - len(prefix),
    )
    if not chunks:
        return [prefix.rstrip("=")]
    return [f"{prefix}{chunks[0]}", *(f"    {chunk}" for chunk in chunks[1:])]


def split_long_value(value: str, *, width: int) -> list[str]:
    if len(value) <= width:
        return [value]

    separator = "/" if "/" in value else "," if "," in value else " "
    if separator == " ":
        tokens = value.split()
    else:
        raw_tokens = value.split(separator)
        tokens = [
            f"{separator}{token}" if index > 0 or value.startswith(separator) else token
            for index, token in enumerate(raw_tokens)
            if token
        ]

    chunks: list[str] = []
    current = ""
    for token in tokens:
        candidate = f"{current}{token}" if separator != " " else f"{current} {token}".strip()
        if current and len(candidate) > width:
            chunks.append(current)
            current = token
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def dedupe_library_logger(logger_name: str) -> None:
    logger = logging.getLogger(logger_name)
    logger.handlers.clear()
    logger.propagate = True


def short_request_id(request_id: Any) -> str:
    return str(request_id).split("-", 1)[0]


def _has_request_context(record: logging.LogRecord) -> bool:
    return all(
        hasattr(record, field)
        for field in ("method", "path", "status_code", "duration_ms")
    )

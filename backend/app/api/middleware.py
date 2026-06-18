"""
File: backend/app/api/middleware.py
Purpose: Provides request observability and lightweight rate limiting.
"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import asdict
import logging
import os
from time import monotonic, perf_counter
from uuid import uuid4

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.exceptions import AppError, RateLimitError
from app.core.observability import DEFAULT_OPERATION_METRICS_RECORDER
from app.schemas import ApiErrorResponse

logger = logging.getLogger("docu_search.api")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Adds request IDs, structured request logs, and operation metrics.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Response],
    ) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid4())
        request.state.request_id = request_id
        operation_name = f"{request.method} {request.url.path}"
        started = perf_counter()

        try:
            response = await call_next(request)
        except AppError as exc:
            DEFAULT_OPERATION_METRICS_RECORDER.record_failure(
                operation_name=operation_name,
                error_code=exc.code,
                duration_ms=duration_ms(started),
            )
            raise
        except Exception:
            DEFAULT_OPERATION_METRICS_RECORDER.record_failure(
                operation_name=operation_name,
                error_code="UNHANDLED_EXCEPTION",
                duration_ms=duration_ms(started),
            )
            raise

        elapsed_ms = duration_ms(started)
        response.headers["X-Request-ID"] = request_id
        if response.status_code >= 400:
            DEFAULT_OPERATION_METRICS_RECORDER.record_failure(
                operation_name=operation_name,
                error_code=str(response.status_code),
                duration_ms=elapsed_ms,
            )
        else:
            DEFAULT_OPERATION_METRICS_RECORDER.record_success(
                operation_name=operation_name,
                duration_ms=elapsed_ms,
            )

        logger.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": elapsed_ms,
            },
        )
        return response


class InMemoryRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple process-local sliding-window limiter.

    It is intentionally lightweight for local production-like deployment. A
    distributed deployment should replace this with a Redis-backed limiter.
    """

    def __init__(self, app, *, requests_per_minute: int | None = None) -> None:
        super().__init__(app)
        configured_limit = os.getenv("API_RATE_LIMIT_PER_MINUTE")
        self.requests_per_minute = requests_per_minute
        if self.requests_per_minute is None:
            self.requests_per_minute = int(configured_limit or "120")
        self._requests: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Response],
    ) -> Response:
        if self.requests_per_minute <= 0 or request.url.path in {"/", "/health"}:
            return await call_next(request)

        key = client_key(request)
        now = monotonic()
        window_start = now - 60
        entries = self._requests[key]
        while entries and entries[0] < window_start:
            entries.popleft()

        if len(entries) >= self.requests_per_minute:
            exc = RateLimitError(
                "Too many requests. Try again shortly.",
                code="RATE_LIMIT_EXCEEDED",
                details={
                    "requests_per_minute": self.requests_per_minute,
                },
            )
            return JSONResponse(
                status_code=429,
                content=ApiErrorResponse(
                    code=exc.code,
                    message=exc.message,
                    details=exc.details,
                ).model_dump(mode="json"),
            )

        entries.append(now)
        return await call_next(request)


def metrics_snapshot() -> dict:
    return asdict(DEFAULT_OPERATION_METRICS_RECORDER.snapshot())


def client_key(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def duration_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000, 3)

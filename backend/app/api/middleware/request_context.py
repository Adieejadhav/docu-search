from __future__ import annotations

from collections.abc import Callable
import logging
from time import perf_counter
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.exceptions import AppError
from app.observability import DEFAULT_OPERATION_METRICS_RECORDER

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

        logger.log(
            logging.WARNING if response.status_code >= 400 else logging.INFO,
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


def duration_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000, 3)

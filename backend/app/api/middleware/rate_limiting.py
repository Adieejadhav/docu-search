from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable
from time import monotonic

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.core.exceptions import RateLimitError
from app.schemas import ApiErrorResponse


class InMemoryRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple process-local sliding-window limiter.

    It is intentionally lightweight for local production-like deployment. A
    distributed deployment should replace this with a Redis-backed limiter.
    """

    def __init__(self, app, *, requests_per_minute: int | None = None) -> None:
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        if self.requests_per_minute is None:
            self.requests_per_minute = get_settings().api.rate_limit_per_minute
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


def client_key(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    if request.client:
        return request.client.host
    return "unknown"

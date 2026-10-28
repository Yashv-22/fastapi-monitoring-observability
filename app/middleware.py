"""
Request instrumentation middleware.

Responsibilities:
  - Generate or sanitize X-Request-ID for every request.
  - Measure request duration with a monotonic timer.
  - Record Prometheus counters, histogram, and slow-request counter.
  - Attach request context to structured log output.
  - Catch unhandled exceptions → log + record + return sanitized 500.

The /metrics endpoint is excluded from business-traffic counters to avoid
inflating request statistics with Prometheus scrape traffic.
"""

import time
import uuid
import re
import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

from app.metrics import (
    HTTP_REQUESTS_TOTAL,
    HTTP_REQUEST_DURATION,
    HTTP_SLOW_REQUESTS_TOTAL,
    HTTP_EXCEPTIONS_TOTAL,
    HTTP_REQUESTS_IN_PROGRESS,
    SLOW_REQUEST_THRESHOLD_SECONDS,
)

logger = logging.getLogger("app")

# Paths excluded from business-traffic metrics (Prometheus scrape path)
_EXCLUDED_METRIC_PATHS = {"/metrics"}

# Regex for sanitizing incoming X-Request-ID header values
_REQUEST_ID_PATTERN = re.compile(r"^[a-zA-Z0-9\-]{1,64}$")


def _sanitize_request_id(raw: str | None) -> str:
    """Accept a clean alphanumeric request ID or generate a new UUID4."""
    if raw and _REQUEST_ID_PATTERN.match(raw):
        return raw
    return str(uuid.uuid4())


def _normalize_route(request: Request) -> str:
    """
    Return the matched route template (e.g. '/users') instead of the full URL.
    Uses a constant for unmatched paths so arbitrary URLs cannot create
    unbounded Prometheus label cardinality.
    """
    if request.scope.get("route"):
        return request.scope["route"].path
    return "__unmatched__"


class InstrumentationMiddleware(BaseHTTPMiddleware):
    """Measure, count, and log every HTTP request."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # --- Request ID ---
        request_id = _sanitize_request_id(
            request.headers.get("x-request-id")
        )

        route = _normalize_route(request)
        request.state.request_id = request_id
        method = request.method

        # Skip metrics inflation from Prometheus scrapes
        skip_metrics = request.url.path in _EXCLUDED_METRIC_PATHS

        if not skip_metrics:
            HTTP_REQUESTS_IN_PROGRESS.inc()

        start_time = time.monotonic()
        status_code = 500  # default in case of unhandled exception

        try:
            response = await call_next(request)
            status_code = response.status_code
            route = _normalize_route(request)
            response.headers["X-Request-ID"] = request_id
            return response

        except Exception as exc:
            route = _normalize_route(request)
            # Unhandled exception — log full details server-side
            logger.error(
                "Unhandled exception during request processing",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "route": route,
                    "error_category": "unhandled_exception",
                    "exception_type": type(exc).__name__,
                },
                exc_info=True,
            )
            if not skip_metrics:
                HTTP_EXCEPTIONS_TOTAL.labels(
                    route=route, exception_type=type(exc).__name__
                ).inc()

            # Return sanitized error to caller — never expose stack trace
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal server error",
                    "request_id": request_id,
                },
                headers={"X-Request-ID": request_id},
            )

        finally:
            duration = time.monotonic() - start_time
            duration_ms = round(duration * 1000, 2)

            if not skip_metrics:
                HTTP_REQUESTS_IN_PROGRESS.dec()
                HTTP_REQUESTS_TOTAL.labels(
                    route=route, method=method, status_code=str(status_code)
                ).inc()
                HTTP_REQUEST_DURATION.labels(route=route, method=method).observe(
                    duration
                )

                # Dedicated slow-request counter for deterministic alerting
                if duration > SLOW_REQUEST_THRESHOLD_SECONDS:
                    HTTP_SLOW_REQUESTS_TOTAL.labels(
                        route=route, method=method
                    ).inc()

            # Structured request log
            logger.info(
                f"{method} {route} → {status_code} ({duration_ms}ms)",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "route": route,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                },
            )

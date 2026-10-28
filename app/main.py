"""
FastAPI API Monitoring Dashboard Demo — Main Application

Endpoints (SOURCE-mandated):
  GET /health             — API health status (API-01)
  GET /users              — Sample user data (API-02)
  GET /products           — Sample product data (API-03)
  GET /simulate-error     — Controlled HTTP 500 (API-04)
  GET /simulate-timeout   — Delayed response >3s (API-05)
  GET /simulate-rate-limit— Simulated HTTP 429 (API-06)

Endpoints (DESIGN — proposed):
  GET /protected          — Demo API-key auth for 401 scenario (DR-01)
  GET /metrics            — Prometheus exposition (DR-02)
"""

import asyncio
import logging
import time

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from app.config import settings
from app.sample_data import SAMPLE_USERS, SAMPLE_PRODUCTS
from app.metrics import APP_INFO, HTTP_EXCEPTIONS_TOTAL
from app.middleware import InstrumentationMiddleware
from app.logging_config import setup_logging

# ---------------------------------------------------------------------------
# Application bootstrap
# ---------------------------------------------------------------------------

logger = setup_logging(settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events: startup and shutdown."""
    logger.info(
        f"Application starting: service={settings.SERVICE_NAME} "
        f"host={settings.HOST} port={settings.PORT}"
    )
    yield
    logger.info("Application shutting down")


app = FastAPI(
    title="FastAPI API Monitoring Demo",
    description="Sample REST API with health tracking, performance monitoring, "
    "failure detection, alerting, and root cause analysis.",
    version="1.0.0",
    lifespan=lifespan,
)

# Register instrumentation middleware
app.add_middleware(InstrumentationMiddleware)

# Publish application metadata
APP_INFO.info({"service": settings.SERVICE_NAME, "version": "1.0.0"})


# ---------------------------------------------------------------------------
# SOURCE-MANDATED ENDPOINTS
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """
    Report current API health status (API-01).

    Returns HTTP 200 when healthy, HTTP 503 when in degraded/unhealthy state.
    The health state can be toggled via the HEALTH_STATE environment variable
    to demonstrate service-health-failure detection (F-06).
    """
    if settings.HEALTH_STATE != "healthy":
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "service": settings.SERVICE_NAME,
                "reason": "Health state set to unhealthy for demonstration",
            },
        )
    return {
        "status": "healthy",
        "service": settings.SERVICE_NAME,
        "timestamp": time.time(),
    }


@app.get("/users", tags=["Data"])
async def get_users() -> list[dict]:
    """Return sample user data (API-02). Synthetic data only."""
    return SAMPLE_USERS


@app.get("/products", tags=["Data"])
async def get_products() -> list[dict]:
    """Return sample product data (API-03). Synthetic data only."""
    return SAMPLE_PRODUCTS


@app.get("/simulate-error", tags=["Simulation"])
async def simulate_error(request: Request) -> None:
    """
    Generate a controlled server error (API-04).

    Raises a deliberate exception that the middleware will:
    - Log with full traceback and request ID (server-side only)
    - Increment api_http_requests_total{status_code="500"}
    - Increment api_http_exceptions_total
    - Return a sanitized 500 response to the caller
    """
    request_id = request.state.request_id
    logger.error(
        "Simulated server error triggered",
        extra={
            "request_id": request_id,
            "route": "/simulate-error",
            "method": "GET",
            "error_category": "simulated_server_error",
            "exception_type": "SimulatedServerError",
        },
    )
    raise RuntimeError(
        "Simulated internal server error for monitoring validation"
    )


@app.get("/simulate-timeout", tags=["Simulation"])
async def simulate_timeout(request: Request) -> dict:
    """
    Simulate a delayed API response (API-05).

    The delay is configurable via SIMULATED_DELAY_SECONDS (default 5s).
    - A patient client (timeout > delay) receives HTTP 200 after the delay.
    - A client with a shorter timeout raises a client-side timeout exception.

    Both the delayed 200 and the client timeout are valid test evidence:
    - Delayed 200 proves the response took >3 seconds (latency monitoring).
    - Client timeout proves actual timeout behaviour.
    """
    delay = settings.SIMULATED_DELAY_SECONDS
    logger.info(
        f"Simulating delayed response: {delay}s",
        extra={
            "request_id": request.state.request_id,
            "route": "/simulate-timeout",
            "method": "GET",
            "error_category": "simulated_timeout",
        },
    )
    await asyncio.sleep(delay)
    return {
        "detail": "Response delayed intentionally",
        "delay_seconds": delay,
        "status": "completed",
    }


@app.get("/simulate-rate-limit", tags=["Simulation"])
async def simulate_rate_limit(request: Request) -> None:
    """
    Simulate a rate-limit rejection (API-06).

    Returns HTTP 429 deterministically. This is a simulation endpoint —
    no actual token-bucket or sliding-window rate limiter is required
    by the assignment. The Retry-After header is included as a courtesy.
    """
    logger.warning(
        "Simulated rate limit exceeded",
        extra={
            "request_id": request.state.request_id,
            "route": "/simulate-rate-limit",
            "method": "GET",
            "error_category": "simulated_rate_limit",
        },
    )
    raise HTTPException(
        status_code=429,
        detail="Simulated rate limit exceeded",
        headers={"Retry-After": "60"},
    )


# ---------------------------------------------------------------------------
# DESIGN-PROPOSED ENDPOINTS
# ---------------------------------------------------------------------------

@app.get("/protected", tags=["Authentication"])
async def protected_endpoint(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict:
    """
    Demonstrate API-key authentication (DR-01, RCA-01).

    Requires a valid X-API-Key header matching DEMO_API_KEY.
    - Missing or invalid key → HTTP 401 (authentication failure scenario).
    - Valid key → HTTP 200 with demo data.

    The API key is NEVER logged or returned in responses.
    """
    if not x_api_key or x_api_key != settings.DEMO_API_KEY:
        logger.warning(
            "Authentication failure: invalid or missing API key",
            extra={
                "request_id": request.state.request_id,
                "route": "/protected",
                "method": "GET",
                "error_category": "authentication_failure",
                "status_code": 401,
            },
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key",
        )
    return {
        "message": "Access granted",
        "data": "This is protected demonstration data",
    }


@app.get("/metrics", tags=["Monitoring"], include_in_schema=False)
async def prometheus_metrics() -> Response:
    """
    Expose Prometheus-compatible metrics (DR-02).

    Returns text exposition format. This endpoint is excluded from
    business-traffic counters by the instrumentation middleware.
    """
    from starlette.responses import Response as StarletteResponse

    return StarletteResponse(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )

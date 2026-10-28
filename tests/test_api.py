"""
Unit and API Integration Tests for FastAPI Monitoring Demo Application.
Validates all 6 SOURCE endpoints and 2 DESIGN endpoints, HTTP status codes,
headers, synthetic data integrity, and X-Request-ID correlation.
"""

import pytest
import re
import logging
import time
from httpx import AsyncClient, ASGITransport
from prometheus_client import REGISTRY
from app.main import app
from app.config import settings


@pytest.mark.asyncio
async def test_health_endpoint_healthy():
    """API-01: Verify /health returns 200 OK with healthy status."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == settings.SERVICE_NAME
    assert "timestamp" in data
    assert "X-Request-ID" in response.headers


@pytest.mark.asyncio
async def test_health_endpoint_unhealthy(monkeypatch):
    """A configured unhealthy mode must return a correlated HTTP 503."""
    monkeypatch.setattr(settings, "HEALTH_STATE", "unhealthy")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")

    assert response.status_code == 503
    assert response.json()["status"] == "unhealthy"
    assert response.headers.get("X-Request-ID")


@pytest.mark.asyncio
async def test_slow_response_increments_slow_request_counter(monkeypatch):
    """Responses over three seconds must be counted by instrumentation."""
    monkeypatch.setattr(settings, "SIMULATED_DELAY_SECONDS", 3.05)
    labels = {"route": "/simulate-timeout", "method": "GET"}
    before = REGISTRY.get_sample_value("api_http_slow_requests_total", labels) or 0
    start = time.monotonic()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/simulate-timeout")
    elapsed = time.monotonic() - start

    assert response.status_code == 200
    assert elapsed > 3.0
    after = REGISTRY.get_sample_value("api_http_slow_requests_total", labels) or 0
    assert after == before + 1


@pytest.mark.asyncio
async def test_users_endpoint():
    """API-02: Verify /users returns sample user records."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/users")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 5
    for user in data:
        assert "id" in user
        assert "name" in user
        assert "email" in user
        assert "role" in user


@pytest.mark.asyncio
async def test_products_endpoint():
    """API-03: Verify /products returns sample product records."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/products")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 5
    for product in data:
        assert "id" in product
        assert "name" in product
        assert "price" in product
        assert "in_stock" in product


@pytest.mark.asyncio
async def test_simulate_error_returns_500():
    """API-04: Verify /simulate-error returns sanitized HTTP 500 with request_id."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/simulate-error")
    assert response.status_code == 500
    data = response.json()
    assert data["detail"] == "Internal server error"
    assert "request_id" in data
    # Traceback should NEVER be leaked to API caller
    assert "traceback" not in data
    assert response.headers.get("X-Request-ID") == data["request_id"]


@pytest.mark.asyncio
async def test_simulate_rate_limit_returns_429():
    """API-06: Verify /simulate-rate-limit returns HTTP 429 with Retry-After header."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/simulate-rate-limit")
    assert response.status_code == 429
    assert response.headers.get("Retry-After") == "60"
    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_protected_auth_failure_401():
    """DR-01 / Scenario A: Verify /protected returns 401 when API key is missing or invalid."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Missing key
        resp1 = await ac.get("/protected")
        assert resp1.status_code == 401
        # Invalid key
        resp2 = await ac.get("/protected", headers={"X-API-Key": "invalid-token-12345"})
        assert resp2.status_code == 401


@pytest.mark.asyncio
async def test_protected_auth_success_200():
    """DR-01: Verify /protected returns 200 OK when correct X-API-Key is provided."""
    headers = {"X-API-Key": settings.DEMO_API_KEY}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/protected", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Access granted"


@pytest.mark.asyncio
async def test_request_id_custom_propagation():
    """Verify incoming X-Request-ID header is propagated when valid."""
    custom_id = "test-custom-request-id-999"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health", headers={"X-Request-ID": custom_id})
    assert response.headers.get("X-Request-ID") == custom_id


@pytest.mark.asyncio
async def test_request_id_sanitization():
    """Verify invalid/unsafe X-Request-ID is replaced with a safe UUID4."""
    dirty_id = "bad<script>alert(1)</script>"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health", headers={"X-Request-ID": dirty_id})
    received_id = response.headers.get("X-Request-ID")
    assert received_id != dirty_id
    # Valid UUID pattern
    assert re.match(r"^[0-9a-f\-]{36}$", received_id)


@pytest.mark.asyncio
async def test_authentication_event_log_has_request_id(caplog):
    """Authentication diagnostics must be correlatable with the response."""
    request_id = "auth-correlation-test-123"
    caplog.set_level(logging.WARNING, logger="app")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(
            "/protected", headers={"X-Request-ID": request_id}
        )

    assert response.status_code == 401
    assert any(
        record.getMessage().startswith("Authentication failure")
        and getattr(record, "request_id", None) == request_id
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_simulated_error_event_log_has_response_request_id(caplog):
    """The controlled 500 event log must use the ID generated by middleware."""
    caplog.set_level(logging.ERROR, logger="app")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/simulate-error")

    request_id = response.json()["request_id"]
    assert response.status_code == 500
    assert any(
        record.getMessage() == "Simulated server error triggered"
        and getattr(record, "request_id", None) == request_id
        for record in caplog.records
    )


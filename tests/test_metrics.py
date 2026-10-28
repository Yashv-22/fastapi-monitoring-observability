"""
Metrics Instrumentation and Exposition Tests.
Validates Prometheus metric exposition, RED metric tracking,
slow-request threshold recording, and low-cardinality label compliance.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_metrics_endpoint_accessible():
    """DR-02: Verify /metrics exposes standard Prometheus text exposition format."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers.get("content-type", "")
    content = response.text
    assert "api_http_requests_total" in content
    assert "api_http_request_duration_seconds" in content
    assert "api_http_slow_requests_total" in content
    assert "api_http_exceptions_total" in content
    assert "api_http_requests_in_progress" in content


@pytest.mark.asyncio
async def test_metrics_counter_increments_on_requests():
    """Verify that hitting endpoints increments api_http_requests_total."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Trigger requests
        await ac.get("/users")
        await ac.get("/products")
        await ac.get("/simulate-rate-limit")

        # Fetch metrics
        metrics_resp = await ac.get("/metrics")
        metrics_text = metrics_resp.text

        # Verify route and status labels are present
        assert 'api_http_requests_total{method="GET",route="/users",status_code="200"}' in metrics_text
        assert 'api_http_requests_total{method="GET",route="/products",status_code="200"}' in metrics_text
        assert 'api_http_requests_total{method="GET",route="/simulate-rate-limit",status_code="429"}' in metrics_text


@pytest.mark.asyncio
async def test_metrics_unhandled_exception_recorded():
    """Verify /simulate-error increments api_http_exceptions_total."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.get("/simulate-error")
        metrics_resp = await ac.get("/metrics")
        metrics_text = metrics_resp.text

        assert 'api_http_exceptions_total{exception_type="RuntimeError",route="/simulate-error"}' in metrics_text
        assert 'api_http_requests_total{method="GET",route="/simulate-error",status_code="500"}' in metrics_text


@pytest.mark.asyncio
async def test_metrics_scrape_endpoint_excluded_from_business_metrics():
    """
    Verify /metrics does not inflate business request counters
    (avoiding self-scraping feedback loops).
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/metrics")
        # Ensure route="/metrics" is NOT in the counter
        assert 'route="/metrics"' not in resp.text


@pytest.mark.asyncio
async def test_unmatched_paths_use_bounded_metric_label():
    """Unknown URL paths must not become arbitrary Prometheus labels."""
    path = "/users/private-id-should-not-be-a-label"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(path)
        metrics_resp = await ac.get("/metrics")

    assert response.status_code == 404
    assert 'route="__unmatched__"' in metrics_resp.text
    assert path not in metrics_resp.text


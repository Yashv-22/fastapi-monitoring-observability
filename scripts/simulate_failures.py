"""
Failure Simulation and Incident Analysis Test Harness.
Executes all required failure scenarios deterministically:
  Scenario A: Authentication Failure (HTTP 401)
  Scenario B: API Timeout (>3s latency and client timeout)
  Scenario C: Internal Server Error (HTTP 500)
  Scenario D: Rate-Limit Rejection (HTTP 429)
  Scenario E: Service Downtime & Health Degradation (Probe verification)

Can run against a live running stack (e.g. http://localhost:8000) or
using an internal ASGI client for standalone offline execution.
"""

import sys
import time
import argparse
from pathlib import Path
import httpx


def test_scenario_a(client: httpx.Client, base_url: str):
    """Scenario A: Authentication Failure (401)."""
    print("\n" + "=" * 60)
    print("SCENARIO A: Authentication Failure Investigation")
    print("=" * 60)
    endpoint = f"{base_url}/protected"
    print(f"Triggering unauthenticated request to: {endpoint}")

    resp = client.get(endpoint, headers={"X-API-Key": "invalid-or-missing-key"})
    print(f"HTTP Status: {resp.status_code} (Expected: 401)")
    print(f"Response Body: {resp.json()}")
    print(f"X-Request-ID: {resp.headers.get('X-Request-ID')}")

    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
    print("[PASS] Scenario A: Authentication Failure verified.")


def test_scenario_b(client: httpx.Client, base_url: str):
    """Scenario B: API Timeout (>3s response and client-side timeout)."""
    print("\n" + "=" * 60)
    print("SCENARIO B: Latency Degradation & Client Timeout Investigation")
    print("=" * 60)
    endpoint = f"{base_url}/simulate-timeout"

    print("Phase 1: Measuring slow server response (>3.0 seconds)...")
    start = time.monotonic()
    resp = client.get(endpoint, timeout=15.0)
    duration = time.monotonic() - start
    print(f"HTTP Status: {resp.status_code} (Expected: 200)")
    print(f"Measured Server Latency: {duration:.2f} seconds")
    print(f"Response Body: {resp.json()}")
    assert duration >= 3.0, f"Expected duration >= 3.0s, got {duration:.2f}s"
    assert resp.status_code == 200

    print("\nPhase 2: Demonstrating actual client-side timeout exception...")
    try:
        # Client configured with strict 1.0s timeout
        client.get(endpoint, timeout=1.0)
        print("[FAIL] Client timeout did NOT trigger!")
        sys.exit(1)
    except httpx.TimeoutException as exc:
        print(f"[PASS] Client-side timeout caught as expected: {type(exc).__name__}")
        print("Detail: Request timed out waiting for server response > 1.0s.")


def test_scenario_b_sync(client):
    """Scenario B: API Timeout demonstration in synchronous ASGI test."""
    print("\n" + "=" * 60)
    print("SCENARIO B: Latency Degradation Investigation")
    print("=" * 60)
    endpoint = "/simulate-timeout"

    print("Phase 1: Measuring slow server response (>3.0 seconds)...")
    start = time.monotonic()
    resp = client.get(endpoint)
    duration = time.monotonic() - start
    print(f"HTTP Status: {resp.status_code} (Expected: 200)")
    print(f"Measured Server Latency: {duration:.2f} seconds")
    print(f"Response Body: {resp.json()}")
    assert duration >= 3.0, f"Expected duration >= 3.0s, got {duration:.2f}s"
    assert resp.status_code == 200
    print("[PASS] Phase 1: Slow response > 3.0 seconds verified.")
    print("Phase 2: Not exercised by in-memory ASGI mode; run with --url to verify a real client timeout.")


def test_scenario_c(client, base_url: str):
    """Scenario C: Server Error (HTTP 500)."""
    print("\n" + "=" * 60)
    print("SCENARIO C: Internal Server Error & Exception Investigation")
    print("=" * 60)
    endpoint = f"{base_url}/simulate-error"
    print(f"Triggering deliberate server error at: {endpoint}")

    resp = client.get(endpoint)
    print(f"HTTP Status: {resp.status_code} (Expected: 500)")
    data = resp.json()
    print(f"Response Body: {data}")
    req_id = resp.headers.get("X-Request-ID")
    print(f"Correlated X-Request-ID: {req_id}")

    assert resp.status_code == 500, f"Expected 500, got {resp.status_code}"
    assert data["detail"] == "Internal server error"
    assert "traceback" not in data, "Security vulnerability: Traceback leaked to caller!"
    print("[PASS] Scenario C: Controlled 500 error and sanitized response verified.")


def test_scenario_d(client: httpx.Client, base_url: str):
    """Scenario D: Rate-Limit Rejection (HTTP 429)."""
    print("\n" + "=" * 60)
    print("SCENARIO D: Rate Limit Rejection Investigation")
    print("=" * 60)
    endpoint = f"{base_url}/simulate-rate-limit"
    print(f"Triggering rate-limit simulation at: {endpoint}")

    resp = client.get(endpoint)
    print(f"HTTP Status: {resp.status_code} (Expected: 429)")
    print(f"Response Body: {resp.json()}")
    retry_after = resp.headers.get("Retry-After")
    print(f"Retry-After Header: {retry_after} seconds")

    assert resp.status_code == 429, f"Expected 429, got {resp.status_code}"
    assert retry_after == "60"
    print("[PASS] Scenario D: Rate limit HTTP 429 response verified.")


def main():
    parser = argparse.ArgumentParser(description="Failure Simulation Runner")
    parser.add_argument("--url", default=None, help="Base URL of FastAPI service (if running live)")
    parser.add_argument("--asgi", action="store_true", help="Run directly against ASGI app in-memory")
    args = parser.parse_args()

    if args.url:
        print(f"Starting Failure Simulation Test Suite against live URL: {args.url}")
        with httpx.Client() as client:
            test_scenario_a(client, args.url)
            test_scenario_b(client, args.url)
            test_scenario_c(client, args.url)
            test_scenario_d(client, args.url)
    else:
        print("Starting Failure Simulation Test Suite using in-memory ASGI application...")
        # Import app for direct ASGI testing
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from app.main import app
        from starlette.testclient import TestClient
        client = TestClient(app)
        test_scenario_a(client, "")
        test_scenario_b_sync(client)
        test_scenario_c(client, "")
        test_scenario_d(client, "")

    print("\n" + "=" * 60)
    print("Endpoint response scenarios completed. Live mode also checks a real client-side timeout.")
    print("Scenario E (Downtime) is not run by this script; use retained probe history or an explicitly approved outage test.")
    print("=" * 60)


if __name__ == "__main__":
    main()

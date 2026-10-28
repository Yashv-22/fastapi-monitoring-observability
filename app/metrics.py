"""
Prometheus metric instrumentation.

Metrics follow RED methodology:
  - Rate:     api_http_requests_total (counter by route, method, status_code)
  - Errors:   api_http_exceptions_total (counter by route, exception_type)
  - Duration: api_http_request_duration_seconds (histogram by route, method)

Additional:
  - api_http_slow_requests_total: requests exceeding 3.0s (for deterministic alerting)
  - api_http_requests_in_progress: gauge of concurrent processing

Labels use normalized route templates — never request IDs, user data, or secrets.
"""

from prometheus_client import Counter, Histogram, Gauge, Info

# ---------------------------------------------------------------------------
# Application metrics
# ---------------------------------------------------------------------------

HTTP_REQUESTS_TOTAL = Counter(
    "api_http_requests_total",
    "Total completed HTTP requests",
    ["route", "method", "status_code"],
)

HTTP_REQUEST_DURATION = Histogram(
    "api_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["route", "method"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 3.0, 5.0, 10.0),
)

HTTP_SLOW_REQUESTS_TOTAL = Counter(
    "api_http_slow_requests_total",
    "HTTP requests that took longer than 3.0 seconds",
    ["route", "method"],
)

HTTP_EXCEPTIONS_TOTAL = Counter(
    "api_http_exceptions_total",
    "Total application exceptions during request handling",
    ["route", "exception_type"],
)

HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "api_http_requests_in_progress",
    "Number of HTTP requests currently being processed",
)

# Service metadata
APP_INFO = Info(
    "api_app",
    "Application metadata",
)

# Slow-request threshold in seconds (matches ALERT-02: >3 seconds)
SLOW_REQUEST_THRESHOLD_SECONDS: float = 3.0

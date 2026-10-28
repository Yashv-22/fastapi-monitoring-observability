"""
Configuration and Infrastructure Specification Tests.
Validates YAML/JSON syntax and structural validity of Prometheus, Alertmanager,
Blackbox, Docker Compose, and Grafana dashboard files.
"""

import json
from pathlib import Path
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent


def test_grafana_dashboard_json_valid():
    """Verify Grafana dashboard JSON file is valid JSON and contains required panels."""
    dashboard_file = BASE_DIR / "monitoring" / "grafana" / "dashboards" / "fastapi_monitoring_dashboard.json"
    assert dashboard_file.exists(), "Dashboard JSON file missing"

    with open(dashboard_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "panels" in data
    assert len(data["panels"]) >= 6

    # Extract all panel titles
    titles = [p.get("title") for p in data["panels"] if p.get("title")]

    # Verify 6 mandatory panels from employer specification
    assert any("Status" in t for t in titles), "Missing Service Status panel"
    assert any("Uptime" in t or "Availability" in t for t in titles), "Missing Uptime panel"
    assert any("Average Response Time" in t for t in titles), "Missing Response Time panel"
    assert any("Total" in t and "Requests" in t for t in titles), "Missing Total Requests panel"
    assert any("Failed" in t for t in titles), "Missing Failed Requests panel"
    assert any("Error Trends" in t for t in titles), "Missing Error Trends panel"

    datasource_file = BASE_DIR / "monitoring" / "grafana" / "provisioning" / "datasources" / "prometheus.yml"
    datasource = datasource_file.read_text(encoding="utf-8")
    assert "uid: Prometheus" in datasource

    targets = {
        panel.get("title"): panel.get("targets", [{}])[0].get("expr", "")
        for panel in data["panels"]
        if panel.get("title")
    }
    for title in (
        "API Uptime (Availability %)",
        "Total API Requests",
        "Failed Requests (4xx / 5xx)",
    ):
        assert "$__range" in targets[title], f"{title} must use the selected dashboard range"

    assert "$__range" in targets["Average Response Time"]


def test_dockerfile_exists_and_configured():
    """Verify Dockerfile exists and configures non-root user and healthcheck."""
    dockerfile = BASE_DIR / "Dockerfile"
    assert dockerfile.exists()
    content = dockerfile.read_text(encoding="utf-8")

    assert "HEALTHCHECK" in content
    assert "USER appuser" in content or "USER" in content
    assert "8000" in content


def test_docker_compose_services():
    """Verify docker-compose.yml defines all required services."""
    compose_file = BASE_DIR / "docker-compose.yml"
    assert compose_file.exists()
    content = compose_file.read_text(encoding="utf-8")

    # Verify all 6 core containers are declared
    required_services = ["app:", "prometheus:", "alertmanager:", "blackbox:", "mailpit:", "grafana:"]
    for svc in required_services:
        assert svc in content, f"Service {svc} missing in docker-compose.yml"


def test_alert_rules_yaml_structure():
    """Verify alert_rules.yml declares all required alert types."""
    rules_file = BASE_DIR / "monitoring" / "alert_rules.yml"
    assert rules_file.exists()
    content = rules_file.read_text(encoding="utf-8")

    # Verify alert definitions
    required_alerts = [
        "alert: APIServiceDown",
        "alert: SlowAPIResponses",
        "alert: HTTP500InternalErrors",
        "alert: HighErrorRate",
        "alert: ServiceHealthDegraded",
        "alert: AuthenticationFailureSpike",
        "alert: RateLimitExceededSpike"
    ]
    for alert in required_alerts:
        assert alert in content, f"Alert rule {alert} missing in alert_rules.yml"


def test_alert_expressions_and_local_mailpit_route():
    """Check alert thresholds and the configured local email test route."""
    rules = (BASE_DIR / "monitoring" / "alert_rules.yml").read_text(encoding="utf-8")
    assert "increase(api_http_slow_requests_total[1m]) > 0" in rules
    assert 'status_code="500"' in rules and "rate(api_http_requests_total" in rules
    assert 'status_code=~"5.."' in rules and ") * 100 > 5" in rules
    assert 'probe_http_status_code{job="blackbox-health"} != 200' in rules
    assert 'status_code="401"' in rules
    assert 'status_code="429"' in rules

    alertmanager = (BASE_DIR / "monitoring" / "alertmanager.yml").read_text(encoding="utf-8")
    assert "smtp_smarthost: 'mailpit:1025'" in alertmanager
    assert "email_configs:" in alertmanager
    assert "send_resolved: true" in alertmanager

    compose = (BASE_DIR / "docker-compose.yml").read_text(encoding="utf-8")
    assert "HEALTH_STATE=${HEALTH_STATE:-healthy}" in compose


def test_slack_receiver_uses_compose_secret_file_without_embedding_webhook():
    """Slack support must read its webhook from a mounted runtime secret."""
    alertmanager = (BASE_DIR / "monitoring" / "alertmanager.yml").read_text(encoding="utf-8")
    compose = (BASE_DIR / "docker-compose.yml").read_text(encoding="utf-8")
    env_example = (BASE_DIR / ".env.example").read_text(encoding="utf-8")
    gitignore = (BASE_DIR / ".gitignore").read_text(encoding="utf-8")

    assert alertmanager.count("api_url_file: /run/secrets/slack_webhook_url") == 2
    assert "slack_configs:" in alertmanager
    assert "slack_webhook_url:" in compose
    assert "file: ./.secrets/slack_webhook_url" in compose
    assert "SLACK_WEBHOOK_URL=" in env_example
    assert ".secrets/" in gitignore
    assert "hooks.slack.com/services/" not in alertmanager


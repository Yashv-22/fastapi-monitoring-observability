# FastAPI Monitoring & Observability Dashboard

A self-contained **FastAPI REST API monitoring demo** with six Docker Compose services: FastAPI, Prometheus, Grafana, Alertmanager, Blackbox Exporter, and Mailpit (local SMTP test inbox). It provides health/availability checks, response times, HTTP status monitoring, error trends, seven alert rules, structured logs with request IDs, and controlled failure simulations.

**Submission contents:** runnable source and Docker configuration, dashboard provisioning, tests, two genuine Grafana screenshots, concise runtime evidence, and this README. No live passwords, API keys, or Slack webhooks are included.

## 1. Requirements and setup

- Docker Desktop with Linux containers and Docker Compose v2 (tested previously on Windows with Docker Desktop + WSL2); or equivalent Docker Engine + Compose on Linux/macOS.
- At least **4 GB of free RAM recommended** and internet access on the first run to pull images/dependencies.
- Python **3.12** recommended for optional local execution/tests.
- Ports **8000, 3000, 9090, 9093, 9115, 8025, 1025** must be free on `127.0.0.1`.

Extract the ZIP, open a terminal in the **`fastapi-monitoring`** folder (the folder containing `docker-compose.yml`), and prepare your private environment file.

**Windows PowerShell**:

```powershell
Copy-Item .env.example .env
notepad .env
```

**Linux/macOS**:

```bash
cp .env.example .env
# Edit .env using your editor
```

Set **non-empty** `GRAFANA_ADMIN_USER` and `GRAFANA_ADMIN_PASSWORD` in `.env` (Docker Compose intentionally refuses to start Grafana without them). Change `DEMO_API_KEY` to a private value for the optional `/protected` endpoint. Leave `SLACK_WEBHOOK_URL=` blank if you do not have a webhook. **Never commit or upload `.env`.**

**Important for GitHub clones:** Git does not track `.secrets/` (by design, to keep webhooks private). Before starting Docker Compose, create the required empty local placeholder file. It does not contain a credential.

**Windows PowerShell:**

```powershell
New-Item -ItemType Directory -Force -Path .secrets | Out-Null
if (-not (Test-Path .secrets/slack_webhook_url)) {
    New-Item -ItemType File -Path .secrets/slack_webhook_url | Out-Null
}
```

**Linux/macOS:**

```bash
mkdir -p .secrets
touch .secrets/slack_webhook_url
```

For actual Slack delivery, set `SLACK_WEBHOOK_URL` locally and run the preparation script as documented in section 6. Never commit the resulting secret file.

Start the stack:

```powershell
docker compose config --quiet
docker compose up -d --build
docker compose ps
```

The first run can take a few minutes. Expect **six services**: `app`, `prometheus`, `grafana`, `alertmanager`, `blackbox`, and `mailpit`. App startup must report healthy; allow Prometheus/Grafana 30–60 seconds to populate their panels. Docker publishes all host ports only on `127.0.0.1` (private/local demo, not a public deployment).

## 2. Open the running services

| Service | URL / port |
| --- | --- |
| API health / Swagger UI | http://127.0.0.1:8000/health · http://127.0.0.1:8000/docs |
| Prometheus metrics | http://127.0.0.1:8000/metrics |
| Grafana dashboard | http://127.0.0.1:3000 (sign in with your `.env` Grafana credentials) |
| Prometheus | http://127.0.0.1:9090/targets |
| Alertmanager | http://127.0.0.1:9093 |
| Blackbox Exporter | http://127.0.0.1:9115 |
| Mailpit local email inbox | http://127.0.0.1:8025 (SMTP listens on host port 1025) |

Grafana is **auto-provisioned** with a Prometheus datasource and the `FastAPI API Monitoring & Observability Dashboard` (Dashboards → FastAPI Monitoring). It displays service status, uptime, average response time, total and failed requests, error-rate trends, throughput, latency percentiles, and slow/in-progress requests. The dashboard's values are live and depend on the selected time range and recent traffic; they will **not** exactly match the captured screenshots on a fresh start.

## 3. Architecture and API

```text
Host API clients → FastAPI :8000 → /metrics → Prometheus :9090 → Grafana :3000
                       ↑              ↑             │
     Blackbox :9115 → GET /health ─────┘             └→ Alertmanager :9093
                                                           │       │
                                                   SMTP → Mailpit   └→ Slack (requires webhook)
```

The containers share a private Docker Compose network. Prometheus scrapes the app and Blackbox exporter every 15 seconds; Blackbox probes `/health` independently. Alertmanager sends local email alerts through Mailpit and has a Slack webhook receiver configured.

| Method | API route | Demonstration behavior |
| --- | --- | --- |
| GET | `/health` | HTTP 200 when healthy; HTTP 503 if configured unhealthy |
| GET | `/users` | Five synthetic users |
| GET | `/products` | Five synthetic products |
| GET | `/protected` | HTTP 401 without/with incorrect `X-API-Key`, HTTP 200 with correct key |
| GET | `/simulate-error` | Controlled HTTP 500, sanitized client response, correlated server log |
| GET | `/simulate-timeout` | Intentional ~5-second delay; short client timeout produces a client-side `ReadTimeout` |
| GET | `/simulate-rate-limit` | Controlled HTTP 429 and `Retry-After: 60` (simulation, **not** a real quota algorithm) |
| GET | `/metrics` | Prometheus-formatted instrumented metrics |

Important metric names: `api_http_requests_total`, `api_http_request_duration_seconds`, `api_http_slow_requests_total`, `api_http_exceptions_total`, `api_http_requests_in_progress`, and Blackbox `probe_success`. Structured application logs attach `X-Request-ID` for correlation; exception tracebacks remain server-side.

## 4. Reproduce failure scenarios and investigate root cause

From the project folder, use a terminal with Python installed; `httpx` is required (`python -m pip install -r requirements.txt` if running the harness outside Docker).

```powershell
python scripts/simulate_failures.py --url http://127.0.0.1:8000
```

Or manually with PowerShell (`curl.exe` avoids PowerShell aliases):

```powershell
curl.exe -i http://127.0.0.1:8000/protected
curl.exe -i http://127.0.0.1:8000/simulate-rate-limit
curl.exe -i http://127.0.0.1:8000/simulate-error
curl.exe -i --max-time 10 http://127.0.0.1:8000/simulate-timeout
curl.exe -i --max-time 1 http://127.0.0.1:8000/simulate-timeout
```

- **Authentication (401):** Missing/incorrect API key; see `AuthenticationFailureSpike`, request status counters and `error_category=authentication_failure` in logs. Fix the client credential.
- **Timeout (>3 seconds):** Intentional 5-second async delay; see slow-request count, duration histogram and `SlowAPIResponses`. A one-second client timeout should fail client-side while the server continues processing. Investigate downstream latency in a real system.
- **Server error (500):** Intentional `RuntimeError`; see `HTTP500InternalErrors`, exception counter, and the sanitized response's `request_id`. Correlate with server logs using `docker compose logs app` to inspect the stack trace. Fix the underlying exception in a real incident.
- **Rate limit (429):** Deterministic simulated rejection; see `RateLimitExceededSpike`. Honor `Retry-After`; investigate traffic quotas in real services.
- **Downtime / unhealthy service:** Independent Blackbox failure detection and `APIServiceDown`/`ServiceHealthDegraded`. Historical test evidence is bundled. **Do not intentionally interrupt any currently running service** unless you are authorized to run a downtime drill.

Alert rules are defined in `monitoring/alert_rules.yml` and include API downtime, response time >3 seconds, HTTP 500, increased 5xx error rate, unhealthy status, repeated 401 and repeated 429 observations. Some rules have `for:` hold periods and require traffic/rate windows; allow time for evaluation and alert routing.

## 5. Evidence in this ZIP

The small `evidence/` folder contains authentic output from earlier local runs. It is **not** generated at install time:

- `evidence/grafana/grafana_dashboard_healthy.png` — live healthy dashboard capture.
- `evidence/grafana/grafana_dashboard_failure_simulation.png` — controlled failure traffic with nonzero failed-request count and 401 error trend; separate CLI/runtime evidence covers HTTP 429 and 500.
- `evidence/final_acceptance/failure_scenarios/urgent-live-harness.txt` — HTTP 401/500/429, slow-response and client-timeout results.
- `evidence/final_acceptance/api/request-id-log-correlation-final.txt` — structured logs and request-ID correlation for incidents.
- `evidence/final_acceptance/alerts/health-failure-alert-states.json` and `post-fix-alert-notification-states.json` — controlled alert-state evidence.
- `evidence/final_acceptance/notifications/urgent-mailpit-messages.json` and `urgent-mailpit-summary.json` — actual local firing/resolved notification messages.
- `evidence/final_acceptance/prometheus/targets-final-remediation.json`, `promtool-rules-final.txt`, and `evidence/final_acceptance/alerts/amtool-validation-final.txt` — scrape/configuration checks.
- `evidence/final_acceptance/failure_scenarios/historical-downtime-probe-recovery.json` — previous downtime/recovery test evidence.
- `evidence/final_acceptance/tests/pytest-urgent-rerun.txt` — saved previous Windows test run.

For new installations, rerun scenarios and inspect live Grafana/Prometheus/Mailpit rather than assuming old screenshots represent current activity.

## 6. Notifications — Mailpit and optional Slack

**Local email (works without external credentials):** Alertmanager uses `mailpit:1025` as the SMTP destination. Trigger an alert and wait for its evaluation, routing, and delivery, then open `http://127.0.0.1:8025` to inspect real firing/resolved test emails. Mailpit does **not** deliver to external mailboxes.

**Slack (requires a valid incoming webhook):** Create a Slack Incoming Webhook using your own Slack workspace. Store the URL in your private `.env` as `SLACK_WEBHOOK_URL=...`, then from the project folder run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\prepare_slack_secret.ps1
docker compose up -d --no-deps --force-recreate alertmanager
```

The script writes the webhook into the locally ignored `.secrets/slack_webhook_url`; it is consumed as a Docker Compose secret, not hard-coded in application source. Generate a controlled alert, allow the evaluation/notification window, and verify an **actual** Slack message. Do not share the webhook in bug reports or screenshots.

**Verification limit:** Slack webhook credentials were not provided during this packaging run. The receiver configuration is included, but **successful Slack delivery has not been verified**. With the provided empty secret placeholder, Alertmanager may log failed Slack delivery attempts while Mailpit email continues to work. External SMTP delivery is also unverified; this demo uses local Mailpit by design.

## 7. Tests, troubleshooting, and maintenance

Run local tests:

```powershell
python -m pip install -r requirements.txt -r requirements-test.txt
python -m pytest tests -q
```

The source and the cleaned package both passed **24 tests** in the packaging environment. This environment does not run the user's Windows Docker Desktop instance, so a brand-new six-container deployment was not independently tested during packaging.

Common checks:

```powershell
docker compose ps
docker compose logs --tail 100 app
docker compose logs --tail 100 prometheus
docker compose logs --tail 100 alertmanager
docker compose config --quiet
```

- **Compose refuses to start:** Confirm `.env` exists and both Grafana credentials are non-empty; confirm `.secrets/slack_webhook_url` exists (empty until configured).
- **Grafana data missing:** Allow a minute for scrapes, confirm `http://127.0.0.1:9090/targets` shows the targets UP, and check the Prometheus datasource under Grafana Connections.
- **Alert emails missing:** Check `docker compose logs alertmanager`, the rule's hold period, and Mailpit at port 8025.
- **Slack notifier errors:** The webhook is absent/invalid; follow section 6. This is separate from local SMTP delivery.
- **Port conflict:** Stop the other process or update the **host-side** port binding in `docker-compose.yml` without changing inter-container ports.
- **Incident RCA:** Use `X-Request-ID` from the API response to correlate structured `app` logs with Prometheus counters and alert state.

For routine maintenance, check `/health` and Prometheus targets, review alerts and resource usage, maintain secure credentials, and update Docker images/dependencies in a tested branch. Docker Compose named volumes preserve Grafana/Prometheus/Alertmanager data. Stop the stack with `docker compose down` when finished; **do not use `docker compose down -v`** unless you deliberately want to delete monitoring history.

**Scope:** This is a local demonstration system, not a public/high-availability production deployment. The sample users/products are synthetic and failure routes intentionally return errors.

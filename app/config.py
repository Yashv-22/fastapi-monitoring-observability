"""
Application configuration loaded from environment variables.
Secrets are never hardcoded; use .env or environment injection.
"""

import os


class Settings:
    """Application settings sourced from environment variables."""

    # Service identity
    SERVICE_NAME: str = os.getenv("SERVICE_NAME", "fastapi-monitoring-demo")
    HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("APP_PORT", "8000"))

    # Demo API key for /protected endpoint (authentication failure scenario)
    # NEVER log or expose this value
    DEMO_API_KEY: str = os.getenv("DEMO_API_KEY", "demo-secret-key-change-me")

    # Simulated delay for /simulate-timeout (seconds)
    SIMULATED_DELAY_SECONDS: float = float(
        os.getenv("SIMULATED_DELAY_SECONDS", "5.0")
    )

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

    # Health state — can be toggled for service-health-failure demonstration
    # Set to "unhealthy" to simulate health degradation without stopping the process
    HEALTH_STATE: str = os.getenv("HEALTH_STATE", "healthy")


settings = Settings()

"""
Structured JSON logging with request-ID correlation.

Emits: timestamp, level, request_id, method, route, status_code, duration_ms,
       error_category, exception_type. Never logs credentials or sensitive headers.
"""

import logging
import json
import sys
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Emit structured JSON log lines for machine-parseable diagnostics."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Attach optional request context fields if present
        for field in (
            "request_id",
            "method",
            "route",
            "status_code",
            "duration_ms",
            "error_category",
            "exception_type",
            "client_ip",
        ):
            value = getattr(record, field, None)
            if value is not None:
                log_entry[field] = value

        # Include safe exception info (server-side only)
        if record.exc_info and record.exc_info[1]:
            exc = record.exc_info[1]
            log_entry["exception_type"] = type(exc).__name__
            log_entry["exception_message"] = str(exc)
            # Full traceback stays in server log; never sent to API caller
            log_entry["traceback"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure the application root logger with JSON output."""
    logger = logging.getLogger("app")
    logger.setLevel(getattr(logging, level, logging.INFO))

    # Avoid duplicate handlers on reload
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)

    # Silence noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    return logger

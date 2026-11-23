"""Structured JSON Logging with Correlation IDs and Redaction."""

import json
import logging
import re
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict

# Context variables for request, agent, and workflow tracking
correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="")
agent_execution_id_ctx: ContextVar[str] = ContextVar("agent_execution_id", default="")
workflow_id_ctx: ContextVar[str] = ContextVar("workflow_id", default="")

# Sensitive key patterns to redact
SENSITIVE_PATTERNS = re.compile(
    r"(password|secret|token|api_key|authorization|bearer|cookie|ssn|credit_card)",
    re.IGNORECASE,
)


def redact_sensitive_data(data: Any) -> Any:
    """Recursively redact sensitive key values from logs."""
    if isinstance(data, dict):
        redacted = {}
        for k, v in data.items():
            if SENSITIVE_PATTERNS.search(str(k)):
                redacted[k] = "[REDACTED]"
            else:
                redacted[k] = redact_sensitive_data(v)
        return redacted
    elif isinstance(data, list):
        return [redact_sensitive_data(item) for item in data]
    return data


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_record: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "correlation_id": correlation_id_ctx.get(),
            "agent_execution_id": agent_execution_id_ctx.get(),
            "workflow_id": workflow_id_ctx.get(),
        }

        if hasattr(record, "extra_fields") and isinstance(record.extra_fields, dict):
            log_record.update(redact_sensitive_data(record.extra_fields))

        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_record)


def setup_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """Configure application-wide logging."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)
    if log_format == "json":
        console_handler.setFormatter(JSONFormatter())
    else:
        plain_format = (
            "%(asctime)s [%(levelname)s] [%(name)s] [corr=%(correlation_id)s] %(message)s"
        )
        console_handler.setFormatter(logging.Formatter(plain_format))

    root_logger.addHandler(console_handler)

    # Suppress verbose httpx/httpcore request-level info logging (e.g. 404s on public endpoints)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


logger = logging.getLogger("platform")

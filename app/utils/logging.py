"""Structured logging configuration."""

import logging
import sys
from datetime import datetime
from typing import Any

def _json_like_format(record: logging.LogRecord) -> str:
    """Format log record as structured JSON-like string."""
    extra: dict[str, Any] = {}
    if hasattr(record, "session_id"):
        extra["session_id"] = record.session_id
    if hasattr(record, "extra_data"):
        extra.update(record.extra_data)

    base = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "level": record.levelname,
        "message": record.getMessage(),
        "logger": record.name,
    }
    if extra:
        base["extra"] = extra
    return str(base)


class StructuredFormatter(logging.Formatter):
    """Formatter that produces structured log output."""

    def format(self, record: logging.LogRecord) -> str:
        return _json_like_format(record)


def setup_logging() -> logging.Logger:
    """Configure and return application logger."""
    logger = logging.getLogger("honeypot")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def get_logger(name: str = "honeypot") -> logging.Logger:
    """Get logger instance."""
    return logging.getLogger(name)

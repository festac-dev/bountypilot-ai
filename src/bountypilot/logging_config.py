"""Structured logging with secret redaction. Never logs auth material in plaintext."""

from __future__ import annotations

import logging
import sys

from bountypilot.security.redaction import redact_text

# Separate logger so a redaction failure can never recurse into itself.
log = logging.getLogger("bountypilot.redaction")

_REDACTING_FILTER_ATTR = "bountypilot_redaction"


class RedactingFilter(logging.Filter):
    """Strip secret-looking tokens from every log record before emission."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = redact_text(str(record.msg))
            if record.args:
                record.args = tuple(redact_text(str(a)) if isinstance(a, str) else a for a in record.args)
        except Exception:  # pragma: no cover - redaction must never break logging
            log.debug("redaction filter could not process record", exc_info=True)
        return True


class CorrelationFormatter(logging.Formatter):
    """Human-readable format including a correlation id when provided."""

    def format(self, record: logging.LogRecord) -> str:
        corr = getattr(record, "correlation_id", None)
        base = f"{self.formatTime(record)} {record.levelname} {record.getMessage()}"
        return f"{base} [correlation={corr}]" if corr else base


def configure_logging(level: str = "WARNING", debug: bool = False) -> logging.Logger:
    """Configure the bountypilot logger once per process."""
    logger = logging.getLogger("bountypilot")
    if getattr(logger, _REDACTING_FILTER_ATTR, False):
        logger.setLevel(logging.DEBUG if debug else level)
        return logger

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(CorrelationFormatter("%(asctime)s %(levelname)s %(message)s"))
    handler.addFilter(RedactingFilter())
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if debug else level)
    logger.propagate = False
    setattr(logger, _REDACTING_FILTER_ATTR, True)
    return logger


def get_logger(name: str = "bountypilot") -> logging.Logger:
    return logging.getLogger(name)

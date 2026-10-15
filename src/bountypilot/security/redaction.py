"""Secret redaction used by logs, configuration display, exports and reports."""

from __future__ import annotations

import re
from typing import Any

from bountypilot import constants

_REDACTED = "[REDACTED]"

# Patterns for values that look like secrets even outside config keys.
_VALUE_PATTERNS = (
    re.compile(r"(?i)\b(sk-[A-Za-z0-9_-]{16,})\b"),  # OpenAI-style API keys
    re.compile(r"\b([1-9A-HJ-NP-Za-km-z]{43,44})\b"),  # base58 Solana private keys
)


def is_secret_key(key: str) -> bool:
    """True when a configuration key names a secret value."""
    upper = key.upper()
    if upper in constants.CONFIG_KEYS and constants.CONFIG_KEYS[upper].get("secret"):
        return True
    return any(s in upper for s in constants.SECRET_ENV_SUFFIXES)


def redact_value(key: str, value: Any) -> str:
    """Redact a single value based on its key."""
    if value is None:
        return ""
    if is_secret_key(key):
        return _REDACTED if str(value).strip() else ""
    return _redact_text(str(value))


def redact_mapping(mapping: dict[str, Any]) -> dict[str, str]:
    """Return a copy of a config mapping with secrets redacted."""
    return {key: redact_value(key, value) for key, value in mapping.items()}


def redact_text(text: str) -> str:
    """Remove secret-looking tokens from free text (logs, transcripts, reports)."""
    if not text:
        return text
    out = text
    for pattern in _VALUE_PATTERNS:
        out = pattern.sub(_REDACTED, out)
    # key=value and key: value pairs with secret-sounding keys
    out = re.sub(
        r"(?i)(\b(?:[\w.-]*(?:api[_-]?key|token|secret|password|private[_-]?key)[\w.-]*|key)\b\s*[:=]\s*)(\"?)([^\s\",]+)\2",
        r"\1\2" + _REDACTED + r"\2",
        out,
    )
    return out


def _redact_text(text: str) -> str:
    return redact_text(text)

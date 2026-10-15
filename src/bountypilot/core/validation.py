"""Input validation helpers shared by commands and services."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from bountypilot.core.models import validate_bounty_id
from bountypilot.exceptions import SecurityPolicyError, ValidationError

_PATH_TRAVERSAL = re.compile(r"(\.\.|/|\\)")


def bounty_id(value: str) -> str:
    try:
        return validate_bounty_id(value)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc


def non_empty(value: str, label: str, max_len: int = 200000) -> str:
    value = (value or "").strip()
    if not value:
        raise ValidationError(f"{label} must not be empty.")
    if len(value) > max_len:
        raise ValidationError(f"{label} exceeds the maximum length of {max_len} characters.")
    return value


def safe_relative_name(value: str, label: str = "name") -> str:
    """Validate a single path component used inside exports/archives."""
    value = (value or "").strip()
    if not value or _PATH_TRAVERSAL.search(value) or value in (".", ".."):
        raise SecurityPolicyError(f"Unsafe {label}: {value!r}")
    return value


def safe_output_path(base: Path, relative: str) -> Path:
    """Join and verify the result stays inside base (traversal protection)."""
    candidate = (base / relative).resolve()
    base_resolved = base.resolve()
    if not str(candidate).startswith(str(base_resolved)):
        raise SecurityPolicyError(f"Path escapes the allowed directory: {relative!r}")
    return candidate


def optional_int(value: Optional[str], label: str, minimum: int = 0) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        number = int(value)
    except ValueError as exc:
        raise ValidationError(f"{label} must be an integer.") from exc
    if number < minimum:
        raise ValidationError(f"{label} must be >= {minimum}.")
    return number

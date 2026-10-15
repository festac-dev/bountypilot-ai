"""Evidence service: capture terminal evidence with metadata and integrity hashes."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from bountypilot.core import validation
from bountypilot.core.models import Evidence, utc_now_iso
from bountypilot.core.validation import safe_output_path
from bountypilot.exceptions import ValidationError
from bountypilot.logging_config import get_logger
from bountypilot.security.redaction import redact_text
from bountypilot.services.container import AppServices

VALID_KINDS = ("transcript", "command_output", "test_summary", "log", "screenshot", "report")
MAX_CAPTURE_BYTES = 500_000

log = get_logger("bountypilot.evidence")


def _hash_bytes(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


class EvidenceService:
    def __init__(self, services: AppServices) -> None:
        self.services = services

    def _evidence_dir(self) -> Path:
        from bountypilot.security.path_validation import ensure_directory

        return ensure_directory(self.services.settings.data_directory / "evidence")

    def capture_text(
        self,
        kind: str,
        description: str,
        content: str,
        bounty_id: str = "",
        redact: bool = True,
    ) -> dict[str, Any]:
        if kind not in VALID_KINDS:
            raise ValidationError(f"Invalid evidence kind {kind!r}. Valid kinds: {', '.join(VALID_KINDS)}")
        description = validation.non_empty(description, "description", max_len=500)
        if bounty_id:
            bounty_id = validation.bounty_id(bounty_id)
        content = content[:MAX_CAPTURE_BYTES]
        if redact:
            content = redact_text(content)
        digest = _hash_bytes(content.encode("utf-8"))
        stamp = utc_now_iso().replace(":", "").replace("-", "")
        path = safe_output_path(self._evidence_dir(), f"{kind}-{stamp}.txt")
        path.write_text(content, encoding="utf-8")
        evidence_id = self.services.evidence.add(
            Evidence(
                kind=kind,
                description=description,
                content_path=str(path),
                content_hash=digest,
                bounty_id=bounty_id,
                origin="verified_run" if kind != "screenshot" else "user_supplied",
            )
        )
        return {
            "id": evidence_id,
            "kind": kind,
            "path": str(path),
            "sha256": digest,
            "redacted": redact,
            "captured_at": utc_now_iso(),
        }

    def capture_file(self, kind: str, description: str, file_path: str, bounty_id: str = "") -> dict[str, Any]:
        """Register a user-supplied file (e.g. a screenshot) as evidence."""
        if kind not in VALID_KINDS:
            raise ValidationError(f"Invalid evidence kind {kind!r}. Valid kinds: {', '.join(VALID_KINDS)}")
        source = Path(file_path).expanduser()
        if not source.is_file():
            raise ValidationError(f"File not found: {file_path}")
        source = source.resolve()
        data = source.read_bytes()[:MAX_CAPTURE_BYTES]
        if bounty_id:
            bounty_id = validation.bounty_id(bounty_id)
        digest = _hash_bytes(data)
        dest = safe_output_path(self._evidence_dir(), f"{kind}-{source.name}")
        dest.write_bytes(data)
        evidence_id = self.services.evidence.add(
            Evidence(
                kind=kind,
                description=validation.non_empty(description, "description", max_len=500),
                content_path=str(dest),
                content_hash=digest,
                bounty_id=bounty_id,
                origin="user_supplied",
            )
        )
        return {
            "id": evidence_id,
            "kind": kind,
            "path": str(dest),
            "sha256": digest,
            "origin": "user_supplied",
            "captured_at": utc_now_iso(),
        }

    def list(self) -> list[dict[str, Any]]:
        return [e.to_dict() for e in self.services.evidence.list()]

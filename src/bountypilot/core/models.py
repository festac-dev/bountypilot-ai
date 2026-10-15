"""Core models: stable, strictly validated, with provenance labels."""

from __future__ import annotations

import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Optional

UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

# Origin labels distinguishing data provenance (section 11 of the build spec).
ORIGIN_PROVIDER = "provider"  # retrieved from Gibwork
ORIGIN_LOCAL_CACHE = "local_cache"  # locally stored copy of provider data
ORIGIN_USER = "user"  # user-supplied notes / attestation
ORIGIN_AI_ESTIMATE = "ai_estimate"  # AI/heuristic generated estimate (not verified)
ORIGIN_VERIFIED_RUN = "verified_run"  # actually executed locally with success observed


def utc_now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def validate_bounty_id(bounty_id: str) -> str:
    bounty_id = (bounty_id or "").strip()
    if not UUID_RE.match(bounty_id):
        raise ValueError(f"Invalid bounty id: {bounty_id!r}. Expected a UUID.")
    return bounty_id.lower()


@dataclass
class Bounty:
    """A bounty retrieved from Gibwork (or a locally cached copy)."""

    id: str
    title: str
    content: str = ""
    deadline: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    status: str = ""
    is_open: bool = True
    reward_amount: Optional[float] = None
    reward_symbol: str = ""
    remaining_amount: Optional[float] = None
    poster_username: str = ""
    url: str = ""
    origin: str = ORIGIN_PROVIDER
    retrieved_at: str = field(default_factory=utc_now_iso)

    @classmethod
    def from_api(cls, raw: dict[str, Any], base_url: str = "https://gib.work") -> Bounty:
        """Build a validated model from a documented public-API record.

        The explore endpoint returns: id, title, content, deadline, tags, status,
        isOpen, remainingAmount, asset/token, user. Missing fields are tolerated.
        """
        bounty_id = str(raw.get("id", "")).strip()
        if not UUID_RE.match(bounty_id):
            raise ValueError(f"Gibwork returned an invalid bounty id: {bounty_id!r}")
        asset = raw.get("asset") or {}
        token = raw.get("token") or {}
        symbol = asset.get("symbol") or token.get("symbol") or ""
        amount = asset.get("price") or token.get("price")
        if amount is None and raw.get("remainingAmount") is not None:
            amount = raw.get("remainingAmount")
        user = raw.get("user") or {}
        deadline = raw.get("deadline")
        if deadline is not None and not isinstance(deadline, str):
            deadline = str(deadline)
        return cls(
            id=bounty_id.lower(),
            title=str(raw.get("title", "")).strip() or "(untitled)",
            content=str(raw.get("content", "") or ""),
            deadline=deadline,
            tags=[str(t) for t in (raw.get("tags") or []) if t],
            status=str(raw.get("status", "") or ""),
            is_open=bool(raw.get("isOpen", True)),
            reward_amount=float(amount) if amount is not None else None,
            reward_symbol=str(symbol),
            remaining_amount=(float(raw["remainingAmount"]) if raw.get("remainingAmount") is not None else None),
            poster_username=str(user.get("username", "") or ""),
            url=f"{base_url}/bounty/{bounty_id.lower()}",
            origin=ORIGIN_PROVIDER,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TrackedBounty:
    """A locally tracked opportunity with its own lifecycle status."""

    bounty_id: str
    local_status: str = "saved"
    notes: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Analysis:
    """AI/heuristic analysis of a bounty. Every estimate is labelled as such."""

    bounty_id: str
    provider: str
    summary: str = ""
    requirements: list[str] = field(default_factory=list)
    deliverables: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    difficulty: str = "unknown"
    effort_hours: Optional[float] = None
    created_at: str = field(default_factory=utc_now_iso)
    origin: str = ORIGIN_AI_ESTIMATE

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Reminder:
    bounty_id: str
    message: str
    deadline: Optional[str] = None
    lead_time_hours: int = 48
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Evidence:
    kind: str  # transcript | command_output | test_summary | log | screenshot | report
    description: str
    content_path: str = ""
    content_hash: str = ""
    bounty_id: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    origin: str = ORIGIN_VERIFIED_RUN

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def new_id() -> str:
    return str(uuid.uuid4())

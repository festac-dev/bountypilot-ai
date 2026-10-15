"""Tracking service: local lifecycle management, distinct from provider status."""

from __future__ import annotations

from typing import Any, List

from bountypilot import constants
from bountypilot.core import validation
from bountypilot.exceptions import ValidationError
from bountypilot.services.container import AppServices


class TrackingService:
    def __init__(self, services: AppServices) -> None:
        self.services = services

    def add(self, bounty_id: str, notes: str = "") -> dict[str, Any]:
        bounty_id = validation.bounty_id(bounty_id)
        self.services.tracking.add(bounty_id, notes=notes)
        tracked = self.services.tracking.get(bounty_id)
        return {"tracked": tracked.to_dict() if tracked else None}

    def list(self) -> List[dict[str, Any]]:
        out = []
        for tracked in self.services.tracking.list():
            bounty = self.services.bounties.get(tracked.bounty_id)
            out.append(
                {
                    **tracked.to_dict(),
                    "title": bounty.title if bounty else "(cached bounty unavailable)",
                    "reward": bounty.reward_amount if bounty else None,
                    "reward_symbol": bounty.reward_symbol if bounty else "",
                    "provider_status": bounty.status if bounty else "",
                    "note": "local_status is BountyPilot's own lifecycle state, independent of the provider status.",
                }
            )
        return out

    def show(self, bounty_id: str) -> dict[str, Any]:
        bounty_id = validation.bounty_id(bounty_id)
        tracked = self.services.tracking.get(bounty_id)
        if tracked is None:
            raise ValidationError(f"Bounty {bounty_id} is not tracked. Use 'bountypilot track add {bounty_id}'.")
        bounty = self.services.bounties.get(bounty_id)
        return {
            **tracked.to_dict(),
            "title": bounty.title if bounty else "(cached bounty unavailable)",
            "bounty_url": bounty.url if bounty else "",
        }

    def set_status(self, bounty_id: str, status: str) -> dict[str, Any]:
        bounty_id = validation.bounty_id(bounty_id)
        status = (status or "").strip().lower()
        if status not in constants.TRACK_STATUSES:
            raise ValidationError(f"Invalid status {status!r}. Valid statuses: {', '.join(constants.TRACK_STATUSES)}")
        tracked = self.services.tracking.get(bounty_id)
        if tracked is None:
            raise ValidationError(f"Bounty {bounty_id} is not tracked.")
        allowed = constants.TRACK_STATUS_TRANSITIONS.get(tracked.local_status, set())
        if status not in allowed and status != tracked.local_status:
            raise ValidationError(
                f"Invalid transition {tracked.local_status!r} -> {status!r}. "
                f"Allowed from {tracked.local_status!r}: {', '.join(sorted(allowed)) or '(none)'}"
            )
        self.services.tracking.set_status(bounty_id, status)
        return {"bounty_id": bounty_id, "local_status": status}

    def remove(self, bounty_id: str) -> bool:
        bounty_id = validation.bounty_id(bounty_id)
        return self.services.tracking.remove(bounty_id)

    def export(self) -> List[dict[str, Any]]:
        return self.services.tracking.export_rows()

    def import_rows(self, rows: List[dict], overwrite: bool = False) -> dict[str, int]:
        return self.services.tracking.import_rows(rows, overwrite=overwrite)

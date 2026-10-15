"""Watch configuration service (registration; polling lives in WatcherService)."""

from __future__ import annotations

from typing import Any

from bountypilot.core import validation
from bountypilot.services.container import AppServices


class WatcherConfigService:
    def __init__(self, services: AppServices) -> None:
        self.services = services

    def add(self, bounty_id: str, interval_seconds: int) -> dict[str, Any]:
        bounty_id = validation.bounty_id(bounty_id)
        self.services.watch.add(bounty_id, interval_seconds)
        cfg = self.services.watch.get(bounty_id) or {}
        return {
            "bounty_id": bounty_id,
            "interval_seconds": cfg.get("interval_seconds", interval_seconds),
            "mode": "periodic polling (not real-time monitoring)",
        }

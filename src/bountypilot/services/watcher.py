"""Watcher service: periodic polling with change detection.

This is periodic polling, NOT real-time monitoring. Intervals are bounded and
respect the configured request interval.
"""

from __future__ import annotations

import time
from typing import Any, Callable, List

from bountypilot.core import validation
from bountypilot.exceptions import ValidationError
from bountypilot.services.container import AppServices

MIN_INTERVAL_SECONDS = 60
MAX_INTERVAL_SECONDS = 3600
WATCHED_FIELDS = (
    "deadline",
    "reward_amount",
    "remaining_amount",
    "status",
    "is_open",
    "title",
    "content",
)


class WatcherService:
    def __init__(self, services: AppServices) -> None:
        self.services = services

    def watch_once(self, bounty_id: str) -> dict[str, Any]:
        """Poll once, diff against the cached snapshot, record and return changes."""
        bounty_id = validation.bounty_id(bounty_id)
        cached = self.services.bounties.get(bounty_id)
        if cached is None:
            raise ValidationError(
                f"Bounty {bounty_id} is not cached locally; run 'bountypilot bounty show {bounty_id}' first."
            )
        fresh = self.services.gibwork.get_task(bounty_id)
        self.services.bounties.upsert(fresh)
        changes = []
        for field in WATCHED_FIELDS:
            old_value = getattr(cached, field, None)
            new_value = getattr(fresh, field, None)
            if old_value != new_value:
                self.services.watch.record_change(bounty_id, field, old_value, new_value)
                changes.append({"field": field, "old": old_value, "new": new_value})
        return {"bounty_id": bounty_id, "polled_at": fresh.retrieved_at, "changes": changes}

    def poll_for(
        self,
        bounty_id: str,
        interval_seconds: int,
        iterations: int,
        stop_flag: Callable[[], bool] = lambda: False,
    ) -> List[dict[str, Any]]:
        """Bounded polling loop. iterations>=0; 0 means until stop_flag (max 100)."""
        interval_seconds = max(MIN_INTERVAL_SECONDS, min(int(interval_seconds), MAX_INTERVAL_SECONDS))
        all_changes = []
        count = 0
        limit = iterations if iterations > 0 else 100
        while count < limit and not stop_flag():
            result = self.watch_once(bounty_id)
            if result["changes"]:
                all_changes.append(result)
            count += 1
            if count < limit and not stop_flag():
                time.sleep(interval_seconds)
        return all_changes

    def list(self) -> List[dict[str, Any]]:
        rows = []
        for cfg in self.services.watch.list():
            bounty = self.services.bounties.get(cfg["bounty_id"])
            rows.append(
                {
                    **cfg,
                    "title": bounty.title if bounty else "(cached bounty unavailable)",
                    "change_count": len(self.services.watch.changes_for(cfg["bounty_id"])),
                    "mode": "periodic polling (not real-time)",
                }
            )
        return rows

    def remove(self, bounty_id: str) -> bool:
        bounty_id = validation.bounty_id(bounty_id)
        return self.services.watch.remove(bounty_id)

    def changes(self, bounty_id: str) -> List[dict[str, Any]]:
        bounty_id = validation.bounty_id(bounty_id)
        return self.services.watch.changes_for(bounty_id)

"""Bounty discovery service: list, search, show, filter, recommend, compare.

All data comes from the configured Gibwork client; results are cached locally
(upsert) so retrieval time and provenance are recorded.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any, Optional

from bountypilot.core import validation
from bountypilot.core.models import Bounty
from bountypilot.exceptions import GibworkNotFound, ValidationError
from bountypilot.services.container import AppServices


class BountyService:
    def __init__(self, services: AppServices) -> None:
        self.services = services

    # -- retrieval ------------------------------------------------------------

    def list_remote(
        self,
        page: int = 1,
        limit: int = 15,
        search: str = "",
        tags: Optional[list[str]] = None,
        cache: bool = True,
    ) -> dict[str, Any]:
        started = time.monotonic()
        page_data = self.services.gibwork.explore(page=page, limit=limit, search=search, tags=tags)
        elapsed = round(time.monotonic() - started, 2)
        stored: dict[str, bool] = {}
        if cache:
            for bounty in page_data.results:
                created = self.services.bounties.upsert(bounty)
                stored[bounty.id] = created
        return {
            "source": "gibwork public listing",
            "retrieval_seconds": elapsed,
            "page": page_data.page,
            "limit": page_data.limit,
            "total": page_data.total,
            "last_page": page_data.last_page,
            "note": page_data.note,
            "bounties": [b.to_dict() for b in page_data.results],
        }

    def show(self, bounty_id: str, refresh: bool = False) -> dict[str, Any]:
        bounty_id = validation.bounty_id(bounty_id)
        repo = self.services.bounties
        if not refresh:
            cached = repo.get(bounty_id)
            if cached is not None:
                return {
                    "bounty": cached.to_dict(),
                    "source": "local cache",
                    "retrieval_seconds": 0.0,
                }
        bounty = self.services.gibwork.get_task(bounty_id)
        repo.upsert(bounty)
        return {"bounty": bounty.to_dict(), "source": "gibwork", "retrieval_seconds": None}

    # -- filtering / recommendation ------------------------------------------

    def filter_local(
        self,
        min_reward: Optional[float] = None,
        max_reward: Optional[float] = None,
        tag: Optional[str] = None,
        open_only: bool = True,
    ) -> list[dict[str, Any]]:
        """Filter the locally cached bounties. Only fields that exist are used:
        reward (remainingAmount/asset price), deadline, tags, open status."""
        results = []
        for bounty in self.services.bounties.list(open_only=open_only):
            reward = bounty.remaining_amount if bounty.remaining_amount is not None else bounty.reward_amount
            if min_reward is not None and (reward is None or reward < min_reward):
                continue
            if max_reward is not None and (reward is None or reward > max_reward):
                continue
            if tag and tag.lower() not in [t.lower() for t in bounty.tags]:
                continue
            results.append(bounty.to_dict())
        return results

    def recommend(self, top: int = 5, min_reward: Optional[float] = None) -> dict[str, Any]:
        """Transparent recommendation ranking from real fields only.

        Score breakdown (all inputs are real provider fields, no invented ratings):
          + reward value (normalised against the highest reward in the set)
          + open status bonus
          + remaining pool ratio (remainingAmount / reward)
          - urgency penalty when the deadline is near (if a deadline exists)
        """
        data = self.list_remote(cache=True)
        bounties: list[Bounty] = []
        for raw in data["bounties"]:
            stored = self.services.bounties.get(raw["id"])
            if stored is not None:
                bounties.append(stored)
        if min_reward is not None:
            bounties = [
                b
                for b in bounties
                if (b.remaining_amount if b.remaining_amount is not None else (b.reward_amount or 0)) >= min_reward
            ]
        if not bounties:
            return {"criteria": [], "recommendations": []}

        rewards = [(b.remaining_amount if b.remaining_amount is not None else (b.reward_amount or 0)) for b in bounties]
        max_reward = max(rewards) or 1.0
        now = datetime.now(UTC)
        rows: list[dict[str, Any]] = []
        for bounty, reward in zip(bounties, rewards, strict=False):
            reward_score = round(40.0 * (reward / max_reward), 1)
            open_bonus = 10.0 if bounty.is_open else 0.0
            remaining = bounty.remaining_amount
            pool_ratio = 0.5
            if remaining is not None and bounty.reward_amount:
                pool_ratio = min(1.0, remaining / bounty.reward_amount) if bounty.reward_amount else 0.5
            pool_score = round(20.0 * pool_ratio, 1)
            urgency_penalty = 0.0
            deadline_note = "no deadline published"
            deadline_dt = None
            if bounty.deadline:
                try:
                    deadline_dt = datetime.fromisoformat(bounty.deadline.replace("Z", "+00:00"))
                except ValueError:
                    deadline_dt = None
            if deadline_dt is not None:
                days_left = (deadline_dt - now).total_seconds() / 86400
                deadline_note = f"{max(0, round(days_left, 1))} days left"
                if days_left <= 3:
                    urgency_penalty = 15.0
                elif days_left <= 7:
                    urgency_penalty = 7.5
            total = round(reward_score + open_bonus + pool_score - urgency_penalty, 1)
            rows.append(
                {
                    "bounty_id": bounty.id,
                    "title": bounty.title,
                    "reward": reward,
                    "reward_symbol": bounty.reward_symbol,
                    "open": bounty.is_open,
                    "deadline": bounty.deadline,
                    "deadline_note": deadline_note,
                    "score": total,
                    "score_breakdown": {
                        "reward_points": reward_score,
                        "open_bonus": open_bonus,
                        "pool_points": pool_score,
                        "urgency_penalty": -urgency_penalty,
                    },
                }
            )
        rows.sort(key=lambda r: float(r["score"]), reverse=True)
        return {
            "criteria": "transparent scoring from real fields (reward, open, pool, deadline)",
            "recommendations": rows[:top],
        }

    def compare(self, id1: str, id2: str) -> dict[str, Any]:
        left = self._resolve(id1)
        right = self._resolve(id2)
        return {
            "bounties": [left.to_dict(), right.to_dict()],
            "differences": _diff(left.to_dict(), right.to_dict()),
        }

    def _resolve(self, bounty_id: str) -> Bounty:
        bounty_id = validation.bounty_id(bounty_id)
        cached = self.services.bounties.get(bounty_id)
        if cached is not None:
            return cached
        try:
            return self.services.gibwork.get_task(bounty_id)
        except GibworkNotFound:
            raise ValidationError(f"Bounty {bounty_id} is neither cached nor found on Gibwork.") from None


def _diff(left: dict[str, Any], right: dict[str, Any]) -> list[dict[str, Any]]:
    fields = [
        "title",
        "reward_amount",
        "reward_symbol",
        "remaining_amount",
        "deadline",
        "status",
        "is_open",
        "tags",
    ]
    out = []
    for field in fields:
        lv, rv = left.get(field), right.get(field)
        if lv != rv:
            out.append({"field": field, "id1": lv, "id2": rv})
    return out

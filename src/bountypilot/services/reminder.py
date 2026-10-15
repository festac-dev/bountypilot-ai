"""Reminder service: persistent, timezone-aware local reminders."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from bountypilot.core import validation
from bountypilot.core.models import Reminder
from bountypilot.exceptions import ValidationError
from bountypilot.services.container import AppServices


class ReminderService:
    def __init__(self, services: AppServices) -> None:
        self.services = services

    def add(self, bounty_id: str, lead_time_hours: int = 48) -> dict[str, Any]:
        bounty_id = validation.bounty_id(bounty_id)
        bounty = self.services.bounties.get(bounty_id)
        if bounty is None:
            raise ValidationError(
                f"Bounty {bounty_id} is not stored locally; run 'bountypilot bounty show {bounty_id}' first."
            )
        deadline = bounty.deadline
        message = f"Deadline approaching for bounty {bounty_id[:8]} ({bounty.title[:60]})"
        summary = "No deadline published on Gibwork; reminder stored without a trigger date."
        if deadline:
            try:
                deadline_dt = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
                trigger_at = deadline_dt - timedelta(hours=lead_time_hours)
                summary = (
                    f"Triggers {trigger_at.astimezone().isoformat(timespec='minutes')} "
                    f"({deadline_dt.astimezone().tzinfo}) - {lead_time_hours}h before the deadline."
                )
            except ValueError:
                summary = "Deadline value could not be parsed; reminder stored without a trigger date."
        reminder = Reminder(bounty_id=bounty_id, message=message, deadline=deadline, lead_time_hours=lead_time_hours)
        reminder_id = self.services.reminders.add(reminder)
        return {"id": reminder_id, "message": message, "summary": summary, "deadline": deadline}

    def list(self) -> list[dict[str, Any]]:
        return [r.to_dict() for r in self.services.reminders.list()]

    def remove(self, index_or_id: str) -> bool:
        return self.services.reminders.remove(index_or_id.strip())

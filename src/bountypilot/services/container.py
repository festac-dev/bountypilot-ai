"""Application service container.

Commands depend only on these services; no command touches SQL or provider
details directly (architecture rule from the build spec).
"""

from __future__ import annotations

from typing import Optional

from bountypilot.integrations.ai.base import AIProvider
from bountypilot.integrations.ai.router import get_provider
from bountypilot.integrations.gibwork.client import GibworkClient, create_client
from bountypilot.settings import Settings
from bountypilot.storage.database import Database
from bountypilot.storage.repositories import (
    AnalysisRepository,
    BountyRepository,
    EvidenceRepository,
    ReminderRepository,
    TrackingRepository,
    WatchRepository,
)


class AppServices:
    """Lazy-wired shared services so read-only commands never create files."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._db: Optional[Database] = None
        self._client: Optional[GibworkClient] = None
        self._ai: Optional[AIProvider] = None
        self._bounties: Optional[BountyRepository] = None
        self._tracking: Optional[TrackingRepository] = None
        self._analyses: Optional[AnalysisRepository] = None
        self._reminders: Optional[ReminderRepository] = None
        self._evidence: Optional[EvidenceRepository] = None
        self._watch: Optional[WatchRepository] = None

    @property
    def db(self) -> Database:
        if self._db is None:
            self._db = Database(self.settings.database_path)
            self._db.connect()
        return self._db

    @property
    def gibwork(self) -> GibworkClient:
        if self._client is None:
            self._client = create_client(self.settings)
        return self._client

    @property
    def ai(self) -> AIProvider:
        if self._ai is None:
            self._ai = get_provider(self.settings)
        return self._ai

    @property
    def bounties(self) -> BountyRepository:
        if self._bounties is None:
            self._bounties = BountyRepository(self.db)
        return self._bounties

    @property
    def tracking(self) -> TrackingRepository:
        if self._tracking is None:
            self._tracking = TrackingRepository(self.db, self.bounties)
        return self._tracking

    @property
    def analyses(self) -> AnalysisRepository:
        if self._analyses is None:
            self._analyses = AnalysisRepository(self.db)
        return self._analyses

    @property
    def reminders(self) -> ReminderRepository:
        if self._reminders is None:
            self._reminders = ReminderRepository(self.db)
        return self._reminders

    @property
    def evidence(self) -> EvidenceRepository:
        if self._evidence is None:
            self._evidence = EvidenceRepository(self.db)
        return self._evidence

    @property
    def watch(self) -> WatchRepository:
        if self._watch is None:
            self._watch = WatchRepository(self.db, self.bounties)
        return self._watch

    def close(self) -> None:
        if self._db is not None:
            self._db.close()
            self._db = None

"""AI provider abstraction. Analysis works with no AI key at all (local provider)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from bountypilot.core.models import Analysis, Bounty


class AIProvider(ABC):
    """Common provider interface. Implementations must never execute generated commands."""

    name = "abstract"

    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def analyze(self, bounty: Bounty, focus: str = "full") -> Analysis:
        """Analyze a bounty. `focus` is one of full|skills|difficulty|effort|requirements."""

    def metadata(self) -> dict[str, Any]:
        return {"provider": self.name, "available": self.is_available()}

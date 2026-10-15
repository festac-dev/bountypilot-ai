"""AI provider router: chooses local or remote per configuration, degrades gracefully."""

from __future__ import annotations

from bountypilot.integrations.ai.base import AIProvider
from bountypilot.integrations.ai.local_provider import LocalHeuristicProvider
from bountypilot.logging_config import get_logger

log = get_logger("bountypilot.ai")


def get_provider(settings) -> AIProvider:
    """Return the configured provider; remote failures fall back to local."""
    if settings.ai_provider == "remote":
        try:
            from bountypilot.integrations.ai.remote_provider import RemoteProvider

            provider = RemoteProvider.from_settings(settings)
            if provider.is_available():
                return provider
        except Exception as exc:
            log.info("remote provider unavailable (%s); using local heuristic provider", exc)
    return LocalHeuristicProvider()

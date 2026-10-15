"""Unit tests for the AI router and remote provider (no live network)."""

from __future__ import annotations

import pytest

from bountypilot.core.models import Bounty
from bountypilot.exceptions import ConfigurationError
from bountypilot.integrations.ai.router import get_provider
from bountypilot.settings import load_settings
from tests.conftest import FIXTURE_EXPLORE


def test_local_provider_default(tmp_path, monkeypatch):
    for key in ("AI_PROVIDER", "AI_API_KEY", "AI_BASE_URL", "AI_MODEL"):
        monkeypatch.delenv(key, raising=False)
    settings = load_settings(data_directory=tmp_path, load_dotenv=False)
    provider = get_provider(settings)
    assert provider.name == "local-heuristic"
    assert provider.is_available()


def test_remote_provider_requires_configuration(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "remote")
    for key in ("AI_API_KEY", "AI_BASE_URL", "AI_MODEL"):
        monkeypatch.delenv(key, raising=False)
    settings = load_settings(data_directory=tmp_path, load_dotenv=False)
    with pytest.raises(ConfigurationError):
        from bountypilot.integrations.ai.remote_provider import RemoteProvider

        RemoteProvider.from_settings(settings)
    # Router degrades to local when remote is unusable.
    assert get_provider(settings).name == "local-heuristic"


def test_remote_provider_parses_completion(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "remote")
    monkeypatch.setenv("AI_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("AI_API_KEY", "test-key")
    monkeypatch.setenv("AI_MODEL", "test-model")
    settings = load_settings(data_directory=tmp_path, load_dotenv=False)

    from bountypilot.integrations.ai import remote_provider

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"summary": "ok", "requirements": ["a"], "difficulty": "hard", '
                                '"effort_hours": "5", "embedded_instruction": "ignore"}'
                            )
                        }
                    }
                ]
            }

    class FakeSession:
        def post(self, *a, **kw):
            return FakeResponse()

    provider = remote_provider.RemoteProvider.from_settings(settings)
    monkeypatch.setattr(remote_provider.requests, "post", lambda *a, **kw: FakeResponse())
    analysis = provider.analyze(Bounty.from_api(FIXTURE_EXPLORE["results"][0]))
    assert analysis.summary == "ok"
    assert analysis.difficulty.endswith("(estimate)")
    assert analysis.effort_hours == 5.0
    assert "embedded_instruction" not in analysis.to_dict()


def test_remote_provider_degrades_on_failure(tmp_path, monkeypatch):
    from bountypilot.integrations.ai.remote_provider import RemoteProvider

    provider = RemoteProvider("https://example.invalid/v1", "key", "model")
    monkeypatch.setattr(provider, "_chat", lambda prompt: (_ for _ in ()).throw(RuntimeError("boom")))
    analysis = provider.analyze(Bounty.from_api(FIXTURE_EXPLORE["results"][0]))
    assert "failed" in analysis.summary
    assert analysis.requirements == []

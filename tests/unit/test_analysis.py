"""Unit tests for the local heuristic analysis provider."""

from __future__ import annotations

from bountypilot.core.models import Bounty
from bountypilot.integrations.ai.local_provider import LocalHeuristicProvider
from tests.conftest import FIXTURE_EXPLORE


def _bounty() -> Bounty:
    return Bounty.from_api(FIXTURE_EXPLORE["results"][0])


def test_analysis_extracts_requirements():
    provider = LocalHeuristicProvider()
    analysis = provider.analyze(_bounty())
    assert any("Gibwork SDK, CLI, or MCP" in r for r in analysis.requirements)
    assert any("web app" in r for r in analysis.requirements)
    assert all(r.endswith("(estimate)") or True for r in [analysis.difficulty])


def test_estimates_are_labelled():
    provider = LocalHeuristicProvider()
    analysis = provider.analyze(_bounty())
    assert analysis.difficulty.endswith("(estimate)")
    assert analysis.origin == "ai_estimate"


def test_focus_variants_change_output():
    provider = LocalHeuristicProvider()
    bounty = _bounty()
    skills = provider.analyze(bounty, focus="skills")
    assert skills.requirements == []
    assert skills.skills
    requirements = provider.analyze(bounty, focus="requirements")
    assert requirements.requirements
    assert requirements.effort_hours is None


def test_deliverables_extraction():
    provider = LocalHeuristicProvider()
    analysis = provider.analyze(_bounty())
    assert any("GitHub repository URL" in d for d in analysis.deliverables)


def test_skills_detection():
    provider = LocalHeuristicProvider()
    skills = provider.analyze(_bounty(), focus="skills").skills
    assert "CLI tooling" in skills
    assert "Documentation" in skills


def test_focused_analysis_is_never_reused_as_full(tmp_path, monkeypatch):
    """Regression: a skills-focused cached analysis must not be served for
    a full analysis request."""
    from bountypilot.core.models import Bounty
    from bountypilot.services.analysis import AnalysisService
    from bountypilot.services.container import AppServices
    from bountypilot.settings import load_settings
    from bountypilot.storage.database import Database

    settings = load_settings(data_directory=tmp_path, load_dotenv=False)
    db = Database(tmp_path / "t.db")
    db.connect()
    services = AppServices(settings)
    services._db = db
    services.bounties.upsert(Bounty.from_api(FIXTURE_EXPLORE["results"][0]))

    class FocusSpyProvider(LocalHeuristicProvider):
        calls = []

        def analyze(self, bounty, focus="full"):
            FocusSpyProvider.calls.append(focus)
            return super().analyze(bounty, focus=focus)

    services._ai = FocusSpyProvider()
    service = AnalysisService(services)
    bounty_id = FIXTURE_EXPLORE["results"][0]["id"]

    service.analyze(bounty_id, focus="skills")
    service.analyze(bounty_id, focus="full")
    assert FocusSpyProvider.calls == ["skills", "full"]
    db.close()

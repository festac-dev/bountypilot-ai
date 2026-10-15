"""Analysis, planning and checklist service (AI optional; estimates always labelled)."""

from __future__ import annotations

from typing import Any

from bountypilot.core import validation
from bountypilot.core.models import Analysis, utc_now_iso
from bountypilot.exceptions import ValidationError
from bountypilot.services.container import AppServices

FOCUSES = ("full", "skills", "difficulty", "effort", "requirements")

FOCUS_LABEL = {
    "full": "Complete analysis",
    "skills": "Skills alignment",
    "difficulty": "Technical difficulty",
    "effort": "Estimated effort",
    "requirements": "Requirement extraction",
}


class AnalysisService:
    def __init__(self, services: AppServices) -> None:
        self.services = services

    def analyze(self, bounty_id: str, focus: str = "full", refresh: bool = False) -> dict[str, Any]:
        bounty_id = validation.bounty_id(bounty_id)
        if focus not in FOCUSES:
            raise ValidationError(f"Unknown focus {focus!r}. Choose one of: {', '.join(FOCUSES)}.")
        bounty = self._load_bounty(bounty_id)
        analysis: Analysis | None = None
        if not refresh:
            stored = self.services.analyses.latest_for(bounty_id)
            if stored and stored.get("provider") == self.services.ai.name:
                candidate = Analysis(bounty_id=bounty_id, provider=stored["provider"])
                for key, value in stored.items():
                    if hasattr(candidate, key):
                        setattr(candidate, key, value)
                # Reuse the cache only when the focus matches exactly; a
                # skills-focused payload must never masquerade as a full one.
                if stored.get("_focus") == focus:
                    analysis = candidate
        if analysis is None:
            analysis = self.services.ai.analyze(bounty, focus=focus)
            payload = analysis.to_dict()
            payload["_focus"] = focus
            self.services.analyses.save(analysis)
            stored = payload
        return {
            "bounty": bounty.to_dict(),
            "analysis": stored,
            "label": "All estimates below are heuristic or AI-generated estimates, not verified facts.",
        }

    def plan(self, bounty_id: str) -> dict[str, Any]:
        """Suggested implementation sequence derived from the analysis."""
        result = self.analyze(bounty_id)
        analysis = result["analysis"]
        steps = []
        for index, req in enumerate(analysis.get("requirements", [])[:10], start=1):
            steps.append(
                {
                    "order": index,
                    "step": req,
                    "origin": "ai_estimate",
                }
            )
        if not steps:
            steps = [
                {
                    "order": 1,
                    "step": "No requirements could be extracted; read the bounty text and define steps manually.",
                    "origin": "ai_estimate",
                }
            ]
        plan = {
            "bounty_id": bounty_id,
            "created_at": utc_now_iso(),
            "origin": "ai_estimate",
            "disclaimer": "Suggested sequence generated from heuristic/AI analysis. Review before executing. "
            "BountyPilot never auto-executes any step.",
            "steps": steps,
        }
        return {"plan": plan, "bounty": result["bounty"]}

    def checklist(self, bounty_id: str) -> dict[str, Any]:
        result = self.analyze(bounty_id)
        analysis = result["analysis"]
        items = []
        for req in analysis.get("requirements", [])[:12]:
            items.append({"text": req, "checked": False, "origin": "ai_estimate"})
        for deliverable in analysis.get("deliverables", [])[:8]:
            items.append({"text": f"Deliverable: {deliverable}", "checked": False, "origin": "ai_estimate"})
        return {
            "checklist": {
                "bounty_id": bounty_id,
                "created_at": utc_now_iso(),
                "origin": "ai_estimate",
                "items": items,
                "note": "Checklist items are heuristic extractions; verify each against the bounty text.",
            },
            "bounty": result["bounty"],
        }

    def _load_bounty(self, bounty_id: str):
        cached = self.services.bounties.get(bounty_id)
        if cached is not None:
            return cached
        bounty = self.services.gibwork.get_task(bounty_id)
        self.services.bounties.upsert(bounty)
        return bounty

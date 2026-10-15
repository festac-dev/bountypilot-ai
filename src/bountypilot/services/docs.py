"""Documentation generation service: readme, setup and acceptance docs from real data."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bountypilot.core import validation
from bountypilot.exceptions import ValidationError
from bountypilot.services.container import AppServices


class DocsService:
    def __init__(self, services: AppServices) -> None:
        self.services = services

    def _out_path(self, bounty_id: str, name: str) -> Path:
        from bountypilot.core.validation import safe_output_path
        from bountypilot.security.path_validation import ensure_directory

        directory = ensure_directory(self.services.settings.data_directory / "exports" / "docs")
        return safe_output_path(directory, f"{name}-{bounty_id[:8]}.md")

    def readme(self, bounty_id: str, project_title: str = "") -> dict[str, Any]:
        bounty_id = validation.bounty_id(bounty_id)
        bounty = self._require_bounty(bounty_id)
        analysis = self.services.analyses.latest_for(bounty_id) or {}
        title = project_title or f"Work project for: {bounty.title}"
        content = "\n".join(
            [
                f"# {title}",
                "",
                "## Use Case / Value / Gibwork Toolset Used",
                "",
                f"- **Use case:** {bounty.title} - see the bounty description below.",
                "- **Value:** turn the bounty requirements into a trackable, evidence-backed project.",
                "- **Gibwork toolset used:** Gibwork public API (documented endpoints used by the "
                "official SDK), accessed through BountyPilot's integration adapter.",
                "",
                "## Bounty reference",
                "",
                f"- Bounty ID: `{bounty.id}`",
                f"- URL: {bounty.url}",
                f"- Reward: {bounty.reward_amount} {bounty.reward_symbol}".rstrip(),
                f"- Deadline: {bounty.deadline or 'not published'}",
                "",
                "## Requirements snapshot (retrieved from Gibwork)",
                "",
                f"{bounty.content[:4000]}{'...' if len(bounty.content) > 4000 else ''}",
                "",
                "## Extracted requirements (heuristic estimates)",
                "",
            ]
        )
        reqs = analysis.get("requirements") or []
        content += "\n".join(f"- {r}" for r in reqs) if reqs else "- (run `bountypilot analyze` first)"
        content += "\n"
        path = self._out_path(bounty_id, "readme")
        path.write_text(content, encoding="utf-8")
        return {
            "path": str(path),
            "generated_at": bounty.retrieved_at,
            "note": "Generated document; illustrative sections are marked as such and must be "
            "reviewed before publishing.",
        }

    def setup(self, bounty_id: str) -> dict[str, Any]:
        bounty_id = validation.bounty_id(bounty_id)
        bounty = self._require_bounty(bounty_id)
        content = "\n".join(
            [
                f"# Setup guide: {bounty.title}",
                "",
                "## Prerequisites",
                "",
                "- Python 3.11+",
                "- `pip install bountypilot-ai` or `pip install -e .` from a checkout",
                "",
                "## Configuration",
                "",
                "```bash",
                "bountypilot init",
                "bountypilot doctor",
                "```",
                "",
                "## Environment variables",
                "",
                "See `.env.example` for the documented names and explanations. Secrets are never printed.",
                "",
                "## Verify the Gibwork integration",
                "",
                "```bash",
                "bountypilot gibwork status",
                "bountypilot gibwork test",
                f"bountypilot bounty show {bounty.id}",
                "```",
                "",
                "## Sample output (illustrative, not captured evidence)",
                "",
                "```text",
                "$ bountypilot gibwork test",
                "Gibwork public API is reachable. Listing total: <n>.",
                "```",
                "",
            ]
        )
        path = self._out_path(bounty_id, "setup")
        path.write_text(content, encoding="utf-8")
        return {"path": str(path), "note": "Sample output is illustrative and labelled as such."}

    def acceptance(self, bounty_id: str) -> dict[str, Any]:
        bounty_id = validation.bounty_id(bounty_id)
        bounty = self._require_bounty(bounty_id)
        analysis = self.services.analyses.latest_for(bounty_id) or {}
        content = "\n".join(
            [
                f"# Acceptance criteria: {bounty.title}",
                "",
                "Derived from the bounty text and heuristic analysis. These are suggestions, "
                "not reviewer-confirmed criteria.",
                "",
            ]
        )
        criteria = analysis.get("acceptance_criteria") or []
        content += "\n".join(f"- [ ] {c}" for c in criteria) if criteria else "- [ ] (run `bountypilot analyze` first)"
        content += "\n"
        path = self._out_path(bounty_id, "acceptance")
        path.write_text(content, encoding="utf-8")
        return {"path": str(path)}

    def _require_bounty(self, bounty_id: str):
        bounty = self.services.bounties.get(bounty_id)
        if bounty is None:
            raise ValidationError(
                f"Bounty {bounty_id} is not stored locally; run 'bountypilot bounty show {bounty_id}' first."
            )
        return bounty

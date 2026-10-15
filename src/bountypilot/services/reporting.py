"""Reporting service: Markdown and JSON reports built from real stored data."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bountypilot.core import validation
from bountypilot.core.validation import safe_output_path
from bountypilot.security.path_validation import ensure_directory
from bountypilot.services.container import AppServices


class ReportingService:
    def __init__(self, services: AppServices) -> None:
        self.services = services

    def _exports_dir(self) -> Path:
        return ensure_directory(self.services.settings.data_directory / "exports")

    def generate(self, bounty_id: str) -> dict[str, Any]:
        bounty_id = validation.bounty_id(bounty_id)
        bounty = self.services.bounties.get(bounty_id)
        if bounty is None:
            from bountypilot.exceptions import ValidationError

            raise ValidationError(
                f"Bounty {bounty_id} is not stored locally; run 'bountypilot bounty show {bounty_id}' first."
            )
        analysis = self.services.analyses.latest_for(bounty_id) or {}
        tracked = self.services.tracking.get(bounty_id)
        evidence = [e.to_dict() for e in self.services.evidence.list() if e.bounty_id == bounty_id]
        watch_changes = self.services.watch.changes_for(bounty_id)

        report: dict[str, Any] = {
            "bounty": bounty.to_dict(),
            "analysis": analysis,
            "tracking": tracked.to_dict() if tracked else None,
            "evidence": evidence,
            "watch_changes": watch_changes,
            "generated_at": analysis.get("created_at") or bounty.retrieved_at,
        }
        markdown = self._render_markdown(report)
        json_text = self._render_json(report)
        md_path = safe_output_path(self._exports_dir(), f"report-{bounty_id[:8]}.md")
        json_path = safe_output_path(self._exports_dir(), f"report-{bounty_id[:8]}.json")
        md_path.write_text(markdown, encoding="utf-8")
        json_path.write_text(json_text, encoding="utf-8")
        return {"markdown_path": str(md_path), "json_path": str(json_path), "report": report}

    @staticmethod
    def _render_markdown(report: dict[str, Any]) -> str:
        bounty = report["bounty"]
        lines = [
            f"# Bounty report: {bounty['title']}",
            "",
            f"- Bounty ID: `{bounty['id']}`",
            f"- URL: {bounty.get('url', '')}",
            f"- Reward: {bounty.get('reward_amount')} {bounty.get('reward_symbol', '')}".rstrip(),
            f"- Deadline: {bounty.get('deadline') or 'not published'}",
            f"- Provider status: {bounty.get('status') or 'unknown'}",
            f"- Open: {bounty.get('is_open')}",
            f"- Data origin: {bounty.get('origin')} (retrieved {bounty.get('retrieved_at')})",
            "",
        ]
        analysis = report.get("analysis") or {}
        if analysis:
            lines += ["## Analysis (AI/heuristic estimates - not verified facts)", ""]
            if analysis.get("summary"):
                lines += [analysis["summary"], ""]
            if analysis.get("requirements"):
                lines += ["### Requirements (extracted)", ""]
                lines += [f"- {r}" for r in analysis["requirements"]] + [""]
            if analysis.get("deliverables"):
                lines += ["### Deliverables (extracted)", ""]
                lines += [f"- {d}" for d in analysis["deliverables"]] + [""]
            if analysis.get("skills"):
                lines += [f"**Skills (detected keywords):** {', '.join(analysis['skills'])}", ""]
            lines += [
                f"**Difficulty:** {analysis.get('difficulty', 'unknown')}",
                f"**Estimated effort:** {analysis.get('effort_hours')} hours (estimate)",
                "",
            ]
        tracking = report.get("tracking")
        if tracking:
            lines += [
                "## Local tracking",
                "",
                f"- Local status: {tracking['local_status']}",
                f"- Notes: {tracking.get('notes') or '(none)'}",
                "",
            ]
        evidence = report.get("evidence") or []
        lines += ["## Evidence", ""]
        if evidence:
            lines += [
                f"- {e['kind']}: {e['description']} ({e['content_path']}, {e['content_hash'][:19]}...)"
                for e in evidence
            ]
        else:
            lines += ["- No evidence captured yet (`bountypilot evidence capture`)."]
        lines.append("")
        if report.get("watch_changes"):
            lines += ["## Watch changes", ""]
            lines += [
                f"- {c['changed_at']}: {c['field']} {c['old_value']!r} -> {c['new_value']!r}"
                for c in report["watch_changes"]
            ]
            lines.append("")
        lines += [
            "## Limitations",
            "",
            "- Estimates in this report are heuristic/AI-generated, never verified facts.",
            "- Bounty data is a local snapshot; check the live listing for current state.",
            "",
        ]
        return "\n".join(lines)

    @staticmethod
    def _render_json(report: dict[str, Any]) -> str:
        import json

        return json.dumps(report, indent=2, default=str)

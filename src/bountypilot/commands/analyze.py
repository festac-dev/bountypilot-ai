"""Analysis and planning commands.

Forms supported (spec section 9):
  bountypilot analyze <id>
  bountypilot analyze skills|difficulty|effort|requirements <id>
  bountypilot analyze <id> skills|difficulty|effort|requirements   (equivalent)
  bountypilot plan <id>
  bountypilot checklist <id>
"""

from __future__ import annotations

from typing import Optional

import typer

from bountypilot.commands.context import get_services
from bountypilot.constants import EXIT_USAGE
from bountypilot.exceptions import ValidationError
from bountypilot.output import detail, echo, emit_json, error, escape_markup
from bountypilot.services.analysis import FOCUS_LABEL, FOCUSES, AnalysisService

FOCUS_ALIASES = {"skills", "difficulty", "effort", "requirements"}


def _print_analysis(data: dict, focus_label: str) -> None:
    b, a = data["bounty"], data["analysis"]
    echo(f"[bold]{focus_label}: {escape_markup(b['title'])}[/bold]")
    detail("Bounty ID", b["id"])
    detail("Provider", a.get("provider"))
    echo()
    if a.get("summary"):
        echo(escape_markup(a["summary"]))
        echo()
    if a.get("requirements"):
        echo("[bold]Requirements (extracted):[/bold]")
        for r in a["requirements"]:
            echo(f"  - {escape_markup(r)}")
        echo()
    if a.get("deliverables"):
        echo("[bold]Deliverables (extracted):[/bold]")
        for d in a["deliverables"]:
            echo(f"  - {escape_markup(d)}")
        echo()
    if a.get("skills"):
        detail("Skills detected (keyword-based)", ", ".join(a["skills"]))
    if a.get("difficulty"):
        detail("Difficulty", a["difficulty"])
    if a.get("effort_hours") is not None:
        detail("Effort (estimate)", f"~{a['effort_hours']} hours")
    for unknown in a.get("unknowns", []):
        echo(f"  ? {escape_markup(unknown)}")
    echo()
    echo("[dim]All estimates are heuristic/AI-generated and labelled as such; they are never verified facts.[/dim]")


def analyze(
    bounty_id: str = typer.Argument(..., help="Bounty UUID (or a focus word followed by the UUID)."),
    focus_arg: Optional[str] = typer.Argument(None, help="Optional focus word."),
    focus: str = typer.Option("", "--focus", help="full|skills|difficulty|effort|requirements"),
    refresh: bool = typer.Option(False, "--refresh", help="Re-run instead of reusing the cached analysis."),
) -> None:
    """Analyze a bounty: requirements, deliverables, skills, difficulty, effort."""
    chosen = ""
    ident = bounty_id.strip()
    if ident in FOCUS_ALIASES:
        chosen = ident
        if not focus_arg:
            error(f"'analyze {ident}' expects a bounty id: 'analyze {ident} <id>'.", EXIT_USAGE)
            raise typer.Exit(EXIT_USAGE)
        ident = focus_arg.strip()
    elif focus_arg:
        if focus_arg.strip() in FOCUS_ALIASES:
            chosen = focus_arg.strip()
        else:
            error(
                f"Unknown focus {focus_arg!r}. Valid: {', '.join(sorted(FOCUS_ALIASES))}.",
                EXIT_USAGE,
            )
            raise typer.Exit(EXIT_USAGE)
    if not chosen:
        chosen = focus.strip().lower()
    if chosen and chosen not in FOCUSES:
        error(f"Unknown focus {chosen!r}. Valid: {', '.join(FOCUSES)}.", EXIT_USAGE)
        raise typer.Exit(EXIT_USAGE)
    try:
        data = AnalysisService(get_services()).analyze(ident, focus=chosen or "full", refresh=refresh)
    except ValidationError as exc:
        error(exc.message, exc.exit_code)
        raise typer.Exit(exc.exit_code)
    if get_services().settings.output_format == "json":
        emit_json(data)
        return
    _print_analysis(data, FOCUS_LABEL.get(chosen or "full", "Analysis"))


def plan(bounty_id: str = typer.Argument(...)) -> None:
    """Suggested implementation sequence (never auto-executed)."""
    try:
        data = AnalysisService(get_services()).plan(bounty_id)
    except ValidationError as exc:
        error(exc.message, exc.exit_code)
        raise typer.Exit(exc.exit_code)
    if get_services().settings.output_format == "json":
        emit_json(data)
        return
    plan_data = data["plan"]
    echo(f"[bold]Implementation plan for {plan_data['bounty_id']}[/bold]")
    for step in plan_data["steps"]:
        echo(f"  {step['order']}. {escape_markup(step['step'])}")
    echo()
    echo(f"[dim]{plan_data['disclaimer']}[/dim]")


def checklist(bounty_id: str = typer.Argument(...)) -> None:
    """Build a checklist from extracted requirements and deliverables."""
    try:
        data = AnalysisService(get_services()).checklist(bounty_id)
    except ValidationError as exc:
        error(exc.message, exc.exit_code)
        raise typer.Exit(exc.exit_code)
    if get_services().settings.output_format == "json":
        emit_json(data)
        return
    items = data["checklist"]
    echo(f"[bold]Checklist for {items['bounty_id']}[/bold]")
    for item in items["items"]:
        echo(f"  [ ] {escape_markup(item['text'])}")
    echo()
    echo(f"[dim]{items['note']}[/dim]")

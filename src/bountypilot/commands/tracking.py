"""Tracking commands: add, list, show, status, remove, export, import."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from bountypilot.commands.context import get_context, get_services
from bountypilot.exceptions import BountyPilotError
from bountypilot.output import detail, echo, emit_json, emit_table, error, escape_markup, success
from bountypilot.services.tracking import TrackingService

app = typer.Typer(help="Track your bounty work locally.", no_args_is_help=True)


@app.command("add")
def add(
    bounty_id: str = typer.Argument(...),
    notes: str = typer.Option("", "--notes", help="Free-form local notes."),
) -> None:
    """Track a bounty (must be stored locally first via `bounty show`)."""
    try:
        data = TrackingService(get_services()).add(bounty_id, notes=notes)
    except BountyPilotError as exc:
        error(exc.message, exc.exit_code)
        raise typer.Exit(exc.exit_code)
    success(f"Tracking {bounty_id} (status: saved).")
    if get_context().json_mode:
        emit_json(data)


@app.command("list")
def list_cmd() -> None:
    """List tracked bounties with their local lifecycle status."""
    rows_raw = TrackingService(get_services()).list()
    if get_context().json_mode:
        emit_json(rows_raw)
        return
    rows = [
        [
            t["bounty_id"],
            t["title"][:50],
            t["local_status"],
            f"{t.get('reward') or '-'} {t.get('reward_symbol', '')}".strip(),
            t["provider_status"] or "-",
        ]
        for t in rows_raw
    ]
    emit_table(
        rows,
        "Tracked bounties",
        ["ID", "Title", "Local status", "Reward", "Provider status"],
        rows,
        empty_state="Nothing tracked yet. Use 'bountypilot track add <id>'.",
    )


@app.command("show")
def show(bounty_id: str = typer.Argument(...)) -> None:
    """Show one tracked bounty."""
    try:
        data = TrackingService(get_services()).show(bounty_id)
    except BountyPilotError as exc:
        error(exc.message, exc.exit_code)
        raise typer.Exit(exc.exit_code)
    if get_context().json_mode:
        emit_json(data)
        return
    echo(f"[bold]{escape_markup(data['title'])}[/bold]")
    detail("Bounty ID", data["bounty_id"])
    detail("Local status", data["local_status"])
    detail("URL", data.get("bounty_url"))
    detail("Notes", data.get("notes") or "(none)")
    detail("Tracked since", data.get("created_at"))


@app.command("status")
def status(bounty_id: str = typer.Argument(...), new_status: str = typer.Argument(...)) -> None:
    """Transition a tracked bounty's local status (validated transitions)."""
    try:
        data = TrackingService(get_services()).set_status(bounty_id, new_status)
    except BountyPilotError as exc:
        error(exc.message, exc.exit_code)
        raise typer.Exit(exc.exit_code)
    success(f"Status of {data['bounty_id']} is now {data['local_status']!r}.")


@app.command("remove")
def remove(
    bounty_id: str = typer.Argument(...),
    force: bool = typer.Option(False, "--yes", help="Skip confirmation."),
) -> None:
    """Stop tracking a bounty (removes only the tracking record, not the snapshot)."""
    from bountypilot.output import confirm

    try:
        if not force and not confirm(f"Stop tracking {bounty_id}?", force):
            echo("Aborted.")
            raise typer.Exit(0)
        removed = TrackingService(get_services()).remove(bounty_id)
    except BountyPilotError as exc:
        error(exc.message, exc.exit_code)
        raise typer.Exit(exc.exit_code)
    if removed:
        success(f"Stopped tracking {bounty_id}.")
    else:
        error(f"Bounty {bounty_id} was not tracked.", 1)
        raise typer.Exit(1)


@app.command("export")
def export_cmd(
    path: str = typer.Argument("tracked-bounties.json", help="Output JSON file."),
) -> None:
    """Export tracked bounties to JSON for backup or transfer."""
    rows = TrackingService(get_services()).export()
    out = Path(path).expanduser()
    out.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    success(f"Exported {len(rows)} record(s) to {out}.")


@app.command("import")
def import_cmd(
    path: str = typer.Argument(..., help="JSON file to import."),
    overwrite: bool = typer.Option(False, "--overwrite", help="Update existing records instead of skipping them."),
) -> None:
    """Import tracked bounties; conflicting records are never silently overwritten."""
    source = Path(path).expanduser()
    try:
        rows = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            raise ValueError("expected a JSON array")
    except (OSError, ValueError) as exc:
        error(f"Cannot import {path}: {exc}", 6)
        raise typer.Exit(6)
    stats = TrackingService(get_services()).import_rows(rows, overwrite=overwrite)
    success(f"Import finished: {stats['created']} created, {stats['updated']} updated, {stats['skipped']} skipped.")

"""Project workflow commands: plan, scaffold, inspect, test, audit, report."""

from __future__ import annotations

import typer

from bountypilot.commands.context import get_services
from bountypilot.exceptions import BountyPilotError
from bountypilot.output import detail, echo, emit_json, error, escape_markup, success
from bountypilot.services.project import ProjectService

app = typer.Typer(help="Inspect, test and audit local projects.", no_args_is_help=True)


@app.command("plan")
def plan(bounty_id: str = typer.Argument(...)) -> None:
    """Actionable implementation plan for a bounty (same service as `bountypilot plan`)."""
    try:
        data = ProjectService(get_services()).plan(bounty_id)
    except BountyPilotError as exc:
        error(exc.message, exc.exit_code)
        raise typer.Exit(exc.exit_code)
    if get_services().settings.output_format == "json":
        emit_json(data)
        return
    plan = data["plan"]
    for step in plan["steps"]:
        echo(f"  {step['order']}. {step['step']}")


@app.command("scaffold")
def scaffold(
    path: str = typer.Argument(..., help="Target directory for the skeleton."),
    bounty_id: str = typer.Argument(...),
    force: bool = typer.Option(False, "--force", help="Allow writing into a non-empty directory."),
) -> None:
    """Scaffold a minimal project skeleton from the bounty plan."""
    try:
        data = ProjectService(get_services()).scaffold(path, bounty_id, force=force)
    except BountyPilotError as exc:
        error(exc.message, exc.exit_code)
        raise typer.Exit(exc.exit_code)
    success(f"Scaffolded {data['path']}: {', '.join(data['created']) or 'no new files needed'}.")


@app.command("inspect")
def inspect(path: str = typer.Argument(...)) -> None:
    """Show project structure, config, tests presence (read-only)."""
    try:
        data = ProjectService(get_services()).inspect(path)
    except BountyPilotError as exc:
        error(exc.message, exc.exit_code)
        raise typer.Exit(exc.exit_code)
    if get_services().settings.output_format == "json":
        emit_json(data)
        return
    detail("Path", data["path"])
    detail("Config files", ", ".join(data["config_files"]) or "(none)")
    detail("Tests present", data["has_tests"])
    detail("README", data["has_readme"])
    detail("LICENSE", data["has_license"])
    echo()
    echo("Top-level entries:")
    for entry in data["structure"][:40]:
        echo(f"  {escape_markup(entry)}")


@app.command("test")
def test(
    path: str = typer.Argument(...),
    command: str = typer.Option("", "--command", help="Override the test command (array-style, space separated)."),
) -> None:
    """Run the project's configured test suite and report the real result."""
    try:
        cmd = command.split() if command else None
        data = ProjectService(get_services()).test(path, command=cmd)
    except BountyPilotError as exc:
        error(exc.message, exc.exit_code)
        raise typer.Exit(exc.exit_code)
    if get_services().settings.output_format == "json":
        emit_json(data)
        return
    if not data["ran"]:
        error(data["detail"], 1)
        raise typer.Exit(1)
    if data["timed_out"]:
        error("Test run timed out.", 1)
        raise typer.Exit(1)
    if data["stdout_tail"]:
        echo(data["stdout_tail"])
    if data["ok"]:
        success("Tests passed (process exited 0).")
    else:
        error(
            f"Tests failed (exit code {data['exit_code'] if 'exit_code' in data else 'non-zero'}).",
            1,
        )
        raise typer.Exit(1)


@app.command("audit")
def audit(path: str = typer.Argument(...)) -> None:
    """Static audit: missing docs, absent tests, unsafe patterns (not a security scan)."""
    try:
        data = ProjectService(get_services()).audit(path)
    except BountyPilotError as exc:
        error(exc.message, exc.exit_code)
        raise typer.Exit(exc.exit_code)
    if get_services().settings.output_format == "json":
        emit_json(data)
        return
    if not data["findings"]:
        success("No audit findings from the static checks.")
        return
    for finding in data["findings"]:
        echo(f"  [{finding['severity']}] {escape_markup(finding['finding'])}")
    echo()
    echo(f"[dim]{data['disclaimer']}[/dim]")


@app.command("report")
def report(bounty_id: str = typer.Argument(...)) -> None:
    """Progress report for a bounty (same service as `bountypilot report generate`)."""
    try:
        data = ProjectService(get_services()).report(bounty_id)
    except BountyPilotError as exc:
        error(exc.message, exc.exit_code)
        raise typer.Exit(exc.exit_code)
    success(f"Report written to {data['markdown_path']} and {data['json_path']}.")

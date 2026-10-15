"""Documentation, evidence, report, submission, reminders and watch commands."""

from __future__ import annotations

import typer

from bountypilot.commands.context import get_services
from bountypilot.exceptions import BountyPilotError
from bountypilot.output import detail, echo, emit_json, emit_table, error, escape_markup, success
from bountypilot.services.docs import DocsService
from bountypilot.services.evidence import EvidenceService
from bountypilot.services.reporting import ReportingService
from bountypilot.services.submission import SubmissionService
from bountypilot.services.watcher import WatcherService

docs_app = typer.Typer(help="Generate documentation from stored bounty data.", no_args_is_help=True)
evidence_app = typer.Typer(help="Capture and list submission evidence.", no_args_is_help=True)
report_app = typer.Typer(help="Generate reports.", no_args_is_help=True)
submission_app = typer.Typer(help="Check and package bounty submissions.", no_args_is_help=True)
reminders_app = typer.Typer(help="Local deadline reminders.", no_args_is_help=True)


def _run(service_call, json_payload=None):
    try:
        data = service_call()
    except BountyPilotError as exc:
        error(exc.message, exc.exit_code)
        raise typer.Exit(exc.exit_code)
    if get_services().settings.output_format == "json" and json_payload is not False:
        emit_json(data)
    return data


# --- docs ---------------------------------------------------------------------


@docs_app.command("readme")
def docs_readme(bounty_id: str = typer.Argument(...), title: str = typer.Option("", "--title")):
    """Generate a README draft (starts with the Use Case / Value / Toolset block)."""
    data = _run(lambda: DocsService(get_services()).readme(bounty_id, project_title=title))
    if get_services().settings.output_format != "json":
        success(f"Generated {data['path']}")


@docs_app.command("setup")
def docs_setup(bounty_id: str = typer.Argument(...)):
    """Generate a setup guide draft."""
    data = _run(lambda: DocsService(get_services()).setup(bounty_id))
    if get_services().settings.output_format != "json":
        success(f"Generated {data['path']}")


@docs_app.command("acceptance")
def docs_acceptance(bounty_id: str = typer.Argument(...)):
    """Generate an acceptance-criteria draft."""
    data = _run(lambda: DocsService(get_services()).acceptance(bounty_id))
    if get_services().settings.output_format != "json":
        success(f"Generated {data['path']}")


# --- evidence -------------------------------------------------------------------


@evidence_app.command("capture")
def evidence_capture(
    description: str = typer.Argument(..., help="What this evidence shows."),
    kind: str = typer.Option(
        "command_output",
        "--kind",
        help="transcript|command_output|test_summary|log|screenshot|report",
    ),
    file: str = typer.Option("", "--file", help="Register an existing file (e.g. a screenshot)."),
    bounty_id: str = typer.Option("", "--bounty"),
) -> None:
    """Capture evidence: read stdin/paste text, or register a user-supplied file."""
    import sys

    try:
        if file:
            data = EvidenceService(get_services()).capture_file(kind, description, file, bounty_id=bounty_id)
        else:
            content = sys.stdin.read() if not sys.stdin.isatty() else ""
            if not content:
                echo("Enter/paste the evidence text, end with Ctrl-D (Ctrl-Z on Windows):")
                content = sys.stdin.read()
            data = EvidenceService(get_services()).capture_text(kind, description, content, bounty_id=bounty_id)
    except BountyPilotError as exc:
        error(exc.message, exc.exit_code)
        raise typer.Exit(exc.exit_code)
    if get_services().settings.output_format == "json":
        emit_json(data)
        return
    success(f"Evidence captured ({data['kind']}): {data['path']}")
    detail("SHA-256", data["sha256"][:32] + "...")


@evidence_app.command("list")
def evidence_list() -> None:
    """List captured evidence records."""
    rows_raw = _run(lambda: EvidenceService(get_services()).list())
    if get_services().settings.output_format == "json":
        return
    rows = [[e["created_at"], e["kind"], e["description"][:50], e["content_path"][:60]] for e in rows_raw]
    emit_table(
        rows,
        "Evidence",
        ["Captured", "Kind", "Description", "Stored at"],
        rows,
        empty_state="No evidence captured yet.",
    )


# --- report ---------------------------------------------------------------------


@report_app.command("generate")
def report_generate(bounty_id: str = typer.Argument(...)) -> None:
    """Generate a Markdown + JSON report for a bounty."""
    data = _run(lambda: ReportingService(get_services()).generate(bounty_id))
    if get_services().settings.output_format != "json":
        success(f"Report generated: {data['markdown_path']}")


# --- submission -------------------------------------------------------------------


@submission_app.command("check")
def submission_check(
    bounty_id: str = typer.Argument(...),
    repo_url: str = typer.Option("", "--repo-url", help="Public GitHub repository URL."),
    demo_video_url: str = typer.Option("", "--demo-video-url", help="Demo video URL."),
    project_path: str = typer.Option("", "--project-path", help="Local project directory to verify."),
    discord_sessions: bool = typer.Option(False, "--discord-sessions-attended", help="User attestation."),
    role: bool = typer.Option(False, "--hackathon-role-awarded", help="User attestation."),
    form: bool = typer.Option(False, "--form-submitted", help="User attestation."),
) -> None:
    """Verify evidence of every item the bounty requires (attestations stay unverified)."""
    data = _run(
        lambda: SubmissionService(get_services()).check(
            bounty_id,
            repo_url=repo_url,
            demo_video_url=demo_video_url,
            project_path=project_path,
            discord_sessions_attended=discord_sessions,
            hackathon_role_awarded=role,
            form_submitted=form,
        )
    )
    if get_services().settings.output_format == "json":
        return
    for check in data["checks"]:
        mark = "[green]PASS[/green]" if check["ok"] else "[red]MISS[/red]"
        echo(f"  {mark}  {escape_markup(check['item'])}  \\[{escape_markup(check['evidence'])}]")
    echo()
    echo(f"Readiness: {data['passed']}/{data['total']} items evidenced.")
    if not data["ready"]:
        echo("Owner-only manual tasks (must be done by you; the tool cannot do them):")
        for item in data["owner_only_manual_tasks"]:
            echo(f"  - {escape_markup(item)}")


@submission_app.command("package")
def submission_package(
    bounty_id: str = typer.Argument(...),
    output_dir: str = typer.Option("", "--out", help="Package output directory."),
) -> None:
    """Create an organized package directory + zip archive (never auto-submits)."""
    data = _run(lambda: SubmissionService(get_services()).package(bounty_id, output_dir=output_dir))
    if get_services().settings.output_format != "json":
        success(f"Package created: {data['archive']}")


# --- reminders ----------------------------------------------------------------------


@reminders_app.command("list")
def reminders_list() -> None:
    """List reminders. Note: background execution needs an OS scheduler (cron or Termux)."""
    from bountypilot.services.reminder import ReminderService

    rows_raw = _run(lambda: ReminderService(get_services()).list())
    if get_services().settings.output_format == "json":
        return
    rows = [
        [
            r["bounty_id"] if r["bounty_id"] else "-",
            r["message"][:50],
            r["deadline"] or "-",
            f"{r['lead_time_hours']}h",
        ]
        for r in rows_raw
    ]
    emit_table(
        rows,
        "Reminders",
        ["Bounty", "Message", "Deadline", "Lead time"],
        rows,
        empty_state="No reminders. Add one with 'bountypilot reminders add <id>'.",
    )
    echo(
        "[dim]BountyPilot does not run in the background; schedule "
        "'bountypilot reminders list' with cron or the Termux Job Scheduler.[/dim]"
    )


@reminders_app.command("add")
def reminders_add(
    bounty_id: str = typer.Argument(...),
    lead_hours: int = typer.Option(48, "--lead-hours", min=0, max=24 * 30),
) -> None:
    """Add a deadline reminder for a bounty (timezone-aware when a deadline exists)."""
    from bountypilot.services.reminder import ReminderService

    try:
        data = ReminderService(get_services()).add(bounty_id, lead_time_hours=lead_hours)
    except BountyPilotError as exc:
        error(exc.message, exc.exit_code)
        raise typer.Exit(exc.exit_code)
    success(data["message"])
    detail("Reminder", data.get("summary", ""))


@reminders_app.command("remove")
def reminders_remove(
    index: str = typer.Argument(..., help="Row number from 'reminders list'."),
) -> None:
    """Remove a reminder by its list row number."""
    from bountypilot.services.reminder import ReminderService

    try:
        removed = ReminderService(get_services()).remove(index)
    except BountyPilotError as exc:
        error(exc.message, exc.exit_code)
        raise typer.Exit(exc.exit_code)
    if removed:
        success("Reminder removed.")
    else:
        error("No matching reminder found.", 1)
        raise typer.Exit(1)


# --- watch ---------------------------------------------------------------------------

# `watch` is a single top-level command (spec inventory: `watch <id>`, `watch list`).


def watch_cmd(
    bounty_id: str = typer.Argument(..., help="Bounty UUID, or the literal word 'list'."),
    interval: int = typer.Option(300, "--interval", min=60, max=3600, help="Polling interval in seconds (bounded)."),
    iterations: int = typer.Option(
        1, "--iterations", min=0, help="Number of polls (0 = until Ctrl-C, bounded to 100)."
    ),
    remove: bool = typer.Option(False, "--remove", help="Stop watching the bounty."),
) -> None:
    """watch <id>: register + poll for changes; watch list: show watched bounties.

    This is periodic polling within rate limits, never real-time monitoring.
    """
    from bountypilot.services.watcher_service import WatcherConfigService

    if bounty_id.strip().lower() == "list":
        rows_raw = _run(lambda: WatcherService(get_services()).list())
        if get_services().settings.output_format == "json":
            return
        rows = [[w["bounty_id"], w["title"][:40], f"{w['interval_seconds']}s", w["change_count"]] for w in rows_raw]
        emit_table(
            rows,
            "Watched bounties (periodic polling)",
            ["ID", "Title", "Interval", "Recorded changes"],
            rows,
            empty_state="Nothing watched. Use 'bountypilot watch <id>'.",
        )
        return
    try:
        if remove:
            removed = WatcherService(get_services()).remove(bounty_id)
            if get_services().settings.output_format == "json":
                emit_json({"removed": removed})
                return
            if removed:
                success(f"Stopped watching {bounty_id}.")
            else:
                error(f"Bounty {bounty_id} is not watched.", 1)
                raise typer.Exit(1)
            return
        # Register (idempotent), then poll according to --iterations.
        WatcherConfigService(get_services()).add(bounty_id, interval_seconds=interval)
        results = WatcherService(get_services()).poll_for(bounty_id, interval, iterations)
        if get_services().settings.output_format == "json":
            emit_json({"polls": results})
            return
        if not results:
            success("No changes detected during polling.")
        for result in results:
            detail(f"Poll {result['polled_at']}", f"{len(result['changes'])} change(s)")
            for change in result["changes"]:
                detail(change["field"], f"{change['old']!r} -> {change['new']!r}")
    except BountyPilotError as exc:
        error(exc.message, exc.exit_code)
        raise typer.Exit(exc.exit_code)

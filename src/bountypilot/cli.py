"""CLI application assembly and top-level error handling."""

from __future__ import annotations

import sys
import traceback
from typing import Optional

import click
import typer

from bountypilot import __version__, constants
from bountypilot.commands.context import CliContext, set_context
from bountypilot.exceptions import BountyPilotError
from bountypilot.logging_config import configure_logging
from bountypilot.output import error as out_error

app = typer.Typer(
    name="bountypilot",
    help="Discover opportunities. Evaluate bounties. Execute with confidence.",
    no_args_is_help=True,
    add_completion=True,
)

_context: CliContext = CliContext()


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"bountypilot {__version__}")
        raise typer.Exit(constants.EXIT_OK)


@app.callback()
def main_callback(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show the installed version.",
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Verbose output."),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress informational output."),
    json_output: bool = typer.Option(False, "--json", help="Emit valid JSON (no decoration)."),
    no_color: bool = typer.Option(False, "--no-color", help="Disable coloured output."),
    debug: bool = typer.Option(False, "--debug", help="Debug mode (shows stack traces)."),
    config_dir: Optional[str] = typer.Option(None, "--config", help="Alternate data/config directory."),
) -> None:
    """BountyPilot AI - Gibwork bounty intelligence for the terminal."""
    global _context
    _context = CliContext(
        verbose=verbose,
        quiet=quiet,
        json_mode=json_output,
        no_color=no_color,
        debug=debug,
        data_dir=config_dir,
    )
    set_context(_context)
    if json_output:
        import bountypilot.output as out

        out.set_json_mode(True)
    configure_logging(_context.settings().log_level, debug=debug)


def handle_error(exc: Exception) -> None:
    """Map exceptions to the documented exit-code scheme; no stack traces in normal use."""
    ctx = _context
    if isinstance(exc, BountyPilotError):
        out_error(exc.message, exc.exit_code)
        raise typer.Exit(exc.exit_code)
    if isinstance(exc, typer.Exit):
        raise exc
    if isinstance(exc, click.UsageError):
        out_error(str(exc), constants.EXIT_USAGE)
        raise typer.Exit(constants.EXIT_USAGE)
    if isinstance(exc, KeyboardInterrupt):
        out_error("Interrupted.", constants.EXIT_GENERAL)
        raise typer.Exit(constants.EXIT_GENERAL)
    if ctx.debug:
        traceback.print_exc(file=sys.stderr)
    out_error(f"Unexpected error: {type(exc).__name__}: {exc}", constants.EXIT_GENERAL)
    raise typer.Exit(constants.EXIT_GENERAL)


def build_app() -> typer.Typer:
    """Register all command families (imported lazily to keep startup fast)."""
    from bountypilot.commands import (
        analyze,
        bounty,
        config_cmd,
        general,
        gibwork,
        project,
        tracking,
        workflows,
    )
    from bountypilot.commands.interactive import run_interactive

    app.command("init")(general.init)
    app.command("doctor")(general.doctor)
    app.command("completion")(general.completion)
    app.add_typer(config_cmd.app, name="config")
    app.add_typer(gibwork.app, name="gibwork")
    app.add_typer(bounty.app, name="bounty")
    app.command("analyze")(analyze.analyze)
    app.command("plan")(analyze.plan)
    app.command("checklist")(analyze.checklist)
    app.add_typer(tracking.app, name="track")
    app.add_typer(project.app, name="project")
    app.add_typer(workflows.docs_app, name="docs")
    app.add_typer(workflows.evidence_app, name="evidence")
    app.add_typer(workflows.report_app, name="report")
    app.add_typer(workflows.submission_app, name="submission")
    app.add_typer(workflows.reminders_app, name="reminders")
    app.command("watch")(workflows.watch_cmd)

    @app.command("interactive")
    def interactive_cmd() -> None:
        """Interactive terminal mode using the same commands and services."""
        code = run_interactive()
        raise typer.Exit(code)

    return app


build_app()

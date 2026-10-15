"""Interactive terminal mode: dispatches through the same CLI commands."""

from __future__ import annotations

import shlex

import click
import typer

from bountypilot.cli import build_app
from bountypilot.output import echo, warn

BANNER = """BountyPilot AI interactive mode. Type a command without the 'bountypilot' prefix
(e.g. 'gibwork status', 'bounty list', 'track list'). Commands: help, exit.
"""

HELP_LINES = (
    "Available command families: gibwork, bounty, analyze, plan, checklist, track,",
    "project, docs, evidence, report, submission, reminders, watch, init, doctor, config.",
    "Type '<command> --help' for details, or 'exit'/'quit' (Ctrl-D) to leave.",
)


def run_interactive() -> int:
    """Reads commands from stdin and dispatches them through the regular CLI app.

    Output streams to the terminal exactly as it does for direct invocations.
    Exits or cancels gracefully on 'exit', 'quit', EOF or Ctrl-C.
    """
    app = build_app()
    command = typer.main.get_command(app)  # click.Command
    echo(BANNER)
    while True:
        try:
            line = input("bountypilot> ").strip()
        except (EOFError, KeyboardInterrupt):
            echo()
            echo("Goodbye.")
            return 0
        if not line:
            continue
        if line in {"exit", "quit", ":q"}:
            echo("Goodbye.")
            return 0
        if line in {"help", "?"}:
            for text in HELP_LINES:
                echo(text)
            continue
        try:
            argv = shlex.split(line)
        except ValueError as exc:
            warn(f"Could not parse input: {exc}")
            continue
        try:
            command.main(args=argv, prog_name="bountypilot", standalone_mode=False)
        except typer.Exit as exc:
            code = exc.exit_code
            if code not in (0, None):
                warn(f"command exited with code {code}")
        except click.exceptions.Exit as exc:
            code = exc.exit_code
            if code not in (0, None):
                warn(f"command exited with code {code}")
        except click.exceptions.Abort:
            warn("Aborted.")
        except click.ClickException as exc:
            warn(str(exc))
        except Exception as exc:  # keep the session alive on unexpected errors
            warn(f"Command failed: {type(exc).__name__}: {exc}")

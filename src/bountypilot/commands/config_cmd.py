"""Configuration commands: config show, config set."""

from __future__ import annotations

import typer

from bountypilot.commands.context import get_context
from bountypilot.exceptions import BountyPilotError
from bountypilot.output import detail, echo, emit_json, error, success
from bountypilot.settings import set_setting

app = typer.Typer(help="Inspect and manage configuration.", no_args_is_help=True)


@app.command("show")
def show() -> None:
    """Show the effective configuration with secrets redacted."""
    ctx = get_context()
    settings = ctx.settings()
    if ctx.json_mode:
        emit_json({"values": settings.as_redacted_dict(), "sources": settings.sources})
        return
    echo("Effective configuration (secrets redacted):")
    echo()
    for key, value in settings.as_redacted_dict().items():
        detail(key, value)
    echo()
    echo("Precedence: command line > environment variables > config file > defaults.")
    echo(f"Config file: {settings.data_directory / 'config.json'}")


@app.command("set")
def set_key(key: str = typer.Argument(...), value: str = typer.Argument(...)) -> None:
    """Validate and persist a configuration key."""
    ctx = get_context()
    try:
        settings = ctx.settings()
        set_setting(settings, key, value)
    except BountyPilotError as exc:
        error(exc.message, exc.exit_code)
        raise typer.Exit(exc.exit_code)
    success(f"Saved {key.upper()}.")

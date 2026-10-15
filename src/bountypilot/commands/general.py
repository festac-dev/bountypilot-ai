"""General commands: init, doctor, completion."""

from __future__ import annotations

import typer

from bountypilot import constants
from bountypilot.commands.context import get_context, get_services
from bountypilot.exceptions import ConfigurationError, StorageError
from bountypilot.integrations.gibwork.health import doctor_report
from bountypilot.logging_config import configure_logging
from bountypilot.output import detail, echo, emit_json, error, escape_markup, success
from bountypilot.security.path_validation import ensure_directory
from bountypilot.settings import ConfigFile

app = typer.Typer(help="General setup and diagnostics.", no_args_is_help=True)


@app.command()
def init() -> None:
    """Create the configuration and data structures (idempotent)."""
    ctx = get_context()
    configure_logging(ctx.settings().log_level, debug=ctx.debug)
    settings = ctx.settings()
    data_dir = ensure_directory(settings.data_directory, mode=0o700)
    db_path = settings.database_path
    created_db = False
    if not db_path.exists():
        created_db = True
    services = ctx.services()
    services.db.connect()  # creates + migrates
    services.close()

    config_file = ConfigFile(data_dir / constants.USER_CONFIG_FILE)
    if not config_file.path.exists():
        config_file.save({})  # creates a valid empty config with restrictive permissions
        config_note = f"created {config_file.path}"
    else:
        config_note = f"already present: {config_file.path}"

    if ctx.json_mode:
        emit_json(
            {
                "status": "ok",
                "data_directory": str(data_dir),
                "database": str(db_path),
                "database_created": created_db,
                "config": config_note,
            }
        )
        return
    success("BountyPilot initialized.")
    detail("Data directory", data_dir)
    detail("Database", f"{db_path} ({'created' if created_db else 'already exists'})")
    detail("Config", config_note)
    echo()
    echo("Next steps:")
    echo("  bountypilot doctor           # verify the environment and integration")
    echo("  bountypilot config show      # review effective configuration (secrets redacted)")


@app.command()
def doctor() -> None:
    """Check Python, packages, configuration, database, permissions and Gibwork readiness."""
    ctx = get_context()
    configure_logging(ctx.settings().log_level, debug=ctx.debug)
    try:
        services = get_services()
        report = doctor_report(services.settings, services.gibwork)
    except ConfigurationError as exc:
        error(exc.message, exc.exit_code)
        raise typer.Exit(exc.exit_code)
    except StorageError as exc:
        error(exc.message, exc.exit_code)
        raise typer.Exit(exc.exit_code)
    if ctx.json_mode:
        emit_json(report)
        raise typer.Exit(0 if report["all_ok"] else 1)
    for check in report["checks"]:
        mark = "[green]✔ ok[/green]" if check["ok"] else "[red]✘ fail[/red]"
        echo(f"  {mark}  [bold]{check['name']}:[/bold] {escape_markup(check['detail'])}")
    if not report["all_ok"]:
        raise typer.Exit(1)
    success("All checks passed.")


@app.command()
def completion(shell: str = typer.Argument(..., help="Target shell: bash, zsh, fish.")) -> None:
    """Show how to install shell completion for the supported shells."""
    supported = ("bash", "zsh", "fish")
    if shell not in supported:
        error(
            f"Unsupported shell {shell!r}. Supported shells: {', '.join(supported)}.",
            constants.EXIT_USAGE,
        )
        raise typer.Exit(constants.EXIT_USAGE)
    echo("BountyPilot uses Typer's built-in completion. Install it with:")
    echo()
    echo(f"  bountypilot --show-completion {shell}")
    echo()
    echo("Or activate it for the current session with:")
    echo()
    echo(f'  eval "$(bountypilot --show-completion {shell})"')

"""Gibwork integration commands: status, auth status, capabilities, test, version."""

from __future__ import annotations

import typer

from bountypilot.commands.context import get_context, get_services
from bountypilot.constants import EXIT_OK, EXIT_SERVICE_UNAVAILABLE
from bountypilot.exceptions import GibworkError
from bountypilot.integrations.gibwork.capabilities import describe
from bountypilot.output import detail, echo, emit_json, error, success, warn

app = typer.Typer(help="Gibwork integration diagnostics.", no_args_is_help=True)

auth_app = typer.Typer(help="Authentication state.", no_args_is_help=True)
app.add_typer(auth_app, name="auth")

app.add_typer(auth_app, name="auth")


def _mode_status(ctx) -> tuple[str, str]:
    settings = ctx.settings()
    mode = settings.gibwork_integration_mode
    if mode == "official_cli":
        if not settings.gibwork_cli_path:
            return (
                "Unsupported configuration",
                "GIBWORK_INTEGRATION_MODE=official_cli but GIBWORK_CLI_PATH is not set",
            )
        return "Configured", f"official CLI bridge: {settings.gibwork_cli_path}"
    return "Configured", f"public API: {settings.gibwork_base_url}"


@app.command()
def status() -> None:
    """Show the real integration state without fabricating a connection."""
    ctx = get_context()
    state, note = _mode_status(ctx)
    reachable = None
    error_note = ""
    auth_state = ""
    failover_note = ""
    if state == "Configured":
        try:
            health = get_services().gibwork.health()
            reachable = bool(health.get("reachable"))
            error_note = "" if reachable else str(health.get("error"))
            auth_state = str(health.get("auth_state", ""))
            failover_note = str(health.get("failover_note") or "")
        except GibworkError as exc:
            reachable = False
            error_note = exc.message
    if reachable is True:
        if health.get("authenticated") is False:
            state = "Authentication required"
        else:
            state = "Connected"
    elif reachable is False:
        state = "Temporarily unavailable" if "unavailable" in error_note.lower() else state
    if ctx.json_mode:
        emit_json(
            {
                "state": state,
                "note": note,
                "reachable": reachable,
                "error": error_note,
                "auth_state": auth_state,
                "failover_note": failover_note,
            }
        )
        return
    detail("State", state)
    detail("Mode", note)
    if auth_state:
        detail("Auth", auth_state)
    if failover_note:
        detail("Failover", failover_note)
    if error_note:
        detail("Error", error_note)


@auth_app.command("status")
def auth_status() -> None:
    """Report whether supported authentication is configured, without revealing secrets."""
    ctx = get_context()
    settings = ctx.settings()
    if settings.gibwork_api_key:
        # Check whether the configured credential is actually accepted.
        try:
            health = get_services().gibwork.health()
        except GibworkError as exc:
            error(exc.message, exc.exit_code)
            raise typer.Exit(exc.exit_code)
        auth_state = health.get("auth_state", "configured")
        if auth_state == "rejected":
            state = "Configured but rejected by the provider"
            detail_text = (
                "GIBWORK_API_KEY is set, but Gibwork rejected it. The public read API continues "
                "to work unauthenticated; no documented API-key auth flow exists for this endpoint."
            )
        else:
            state = "Configured"
            detail_text = "GIBWORK_API_KEY is set (value redacted)."
    else:
        if settings.gibwork_integration_mode == "official_cli":
            state = "Authentication required"
            detail_text = (
                "The official Gibwork CLI requires a configured wallet for all task operations, "
                "including public discovery. Configure a keypair through the official CLI "
                "(keypair-path in a profile, --keypair file, or --private-key-stdin)."
            )
        else:
            state = "Authentication required"
            detail_text = (
                "No credential configured. The public read API works unauthenticated for page 1 of the "
                "listing; write operations and deep pagination require an authenticated session, which "
                "the documented public flow does not expose to CLI tools."
            )
    if ctx.json_mode:
        emit_json({"state": state, "detail": detail_text})
        return
    detail("Auth state", state)
    detail("Detail", detail_text)


@app.command()
def capabilities() -> None:
    """List verified operations and explicitly unsupported ones."""
    services = get_services()
    report = describe(services.gibwork)
    if ctx_json_mode():
        emit_json(report)
        return
    echo(f"Integration mode: {report['integration_mode']}")
    echo()
    for operation, status_label in report["operations"].items():
        echo(f"  {operation:<45} {status_label}")
    echo()
    for note in report["notes"]:
        echo(f"  - {note}")


def ctx_json_mode() -> bool:
    from bountypilot.output import json_mode

    return json_mode()


@app.command("test")
def test() -> None:
    """Safe, read-only check of the configured Gibwork integration."""
    services = get_services()
    try:
        health = services.gibwork.health()
    except GibworkError as exc:
        error(exc.message, exc.exit_code)
        raise typer.Exit(exc.exit_code)
    ok = bool(health.get("reachable"))
    payload = {
        "reachable": ok,
        "checked_at": health.get("checked_at"),
        "listing_total": health.get("listing_total"),
        "authenticated": health.get("authenticated"),
        "note": health.get("note"),
        "error": health.get("error"),
        "failover_note": health.get("failover_note"),
    }
    if ctx_json_mode():
        emit_json(payload)
    elif ok:
        total = health.get("listing_total")
        note = health.get("note")
        failover_note = health.get("failover_note")
        if total is not None:
            success(f"Gibwork is reachable. Public listing shows {total} bounties.")
        elif note:
            success(f"Gibwork is reachable. {note}")
        else:
            success("Gibwork is reachable.")
        if failover_note:
            warn(failover_note)
    else:
        hint = ""
        base = services.gibwork.base_url if hasattr(services.gibwork, "base_url") else None
        if base:
            hint = (
                f" If your network blocks {base}, point GIBWORK_BASE_URL at an "
                "alternative host (e.g. https://api2.gib.work)."
            )
        error(f"Gibwork is not reachable: {health.get('error')}{hint}", EXIT_SERVICE_UNAVAILABLE)
    raise typer.Exit(EXIT_OK if ok else EXIT_SERVICE_UNAVAILABLE)


@app.command()
def version() -> None:
    """Show the integration client version, if exposed."""
    services = get_services()
    client_version = services.gibwork.version()
    if ctx_json_mode():
        emit_json({"client_version": client_version})
        return
    detail("Client version", client_version or "not exposed by this integration")

"""Terminal output: rich console, tables, JSON mode, exit codes, empty states."""

from __future__ import annotations

import json as jsonlib
import sys
from typing import Any, Iterable, Optional, Sequence

from rich import box
from rich.console import Console
from rich.markup import escape as rich_escape
from rich.table import Table

from bountypilot.exceptions import UsageError

_console = Console(highlight=False)
_err_console = Console(stderr=True, highlight=False)

_out_mode = {"json": False}


def escape_markup(text: Any) -> str:
    """Escape rich markup so dynamic/untrusted text renders literally.

    Bounty titles and descriptions, file paths and audit findings can contain
    square brackets; rendered unescaped they would be parsed as style tags
    (swallowed text or MarkupError crashes).
    """
    return rich_escape(str(text))


def set_json_mode(enabled: bool) -> None:
    _out_mode["json"] = bool(enabled)


def json_mode() -> bool:
    return _out_mode["json"]


def echo(message: str = "") -> None:
    if json_mode():
        return
    _console.print(message)


def emit_json(payload: Any) -> None:
    """Emit valid JSON with no decoration (guaranteed in JSON mode).

    Written with plain print (not rich) so no console wrapping can corrupt it.
    """
    print(jsonlib.dumps(payload, indent=2, default=str, sort_keys=False))


def emit(payload: Any, fallback_lines: Optional[Sequence[str]] = None) -> None:
    """Emit JSON in JSON mode, otherwise print the human-readable lines."""
    if json_mode():
        emit_json(payload)
    else:
        for line in fallback_lines or []:
            echo(line)


def emit_table(
    payload: Any,
    title: str,
    columns: Sequence[str],
    rows: Iterable[Sequence[Any]],
    empty_state: str = "No records found.",
) -> None:
    """Emit a table (or JSON array) with a helpful empty state."""
    if json_mode():
        emit_json(payload)
        return
    rows = list(rows)
    if not rows:
        echo(f"[dim]{empty_state}[/dim]")
        return
    table = Table(
        title=title,
        box=box.ROUNDED,
        header_style="bold cyan",
        border_style="dim",
        padding=(0, 1),
        show_lines=False,
    )
    for col in columns:
        table.add_column(col, overflow="fold")
    for row in rows:
        table.add_row(*[escape_markup(cell) for cell in row])
    _console.print(table)


def error(message: str, exit_code: int = 1) -> None:
    """Human-readable terminal error with no stack trace."""
    if json_mode():
        print(jsonlib.dumps({"error": message, "exit_code": exit_code}))
    else:
        _err_console.print(f"[bold red]Error:[/bold red] {escape_markup(message)}")


def success(message: str) -> None:
    if json_mode():
        emit_json({"status": "ok", "message": message})
    else:
        echo(f"[bold green]✔[/bold green] {escape_markup(message)}")


def warn(message: str) -> None:
    if not json_mode():
        _err_console.print(f"[yellow]Warning:[/yellow] {escape_markup(message)}")


def detail(label: str, value: Any) -> None:
    if not json_mode():
        echo(f"  [bold]{label}:[/bold] {escape_markup(value)}")


def confirm(prompt: str, assume_yes: bool = False) -> bool:
    """Interactive confirmation; non-interactive defaults to no unless --yes."""
    if assume_yes:
        return True
    if json_mode() or not sys.stdin.isatty():
        return False
    try:
        answer = input(f"{prompt} [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return answer in ("y", "yes")


def require_args(args: Sequence[str], expected: int, usage: str) -> None:
    if len(args) < expected:
        raise UsageError(f"Missing arguments. Usage: {usage}")

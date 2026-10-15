"""Bounty discovery commands: list, search, show, filter, recommend, compare."""

from __future__ import annotations

from typing import Any

import typer

from bountypilot.commands.context import get_context, get_services
from bountypilot.output import detail, echo, emit_json, emit_table, escape_markup
from bountypilot.services.bounty import BountyService

app = typer.Typer(help="Discover and inspect Gibwork bounties.", no_args_is_help=True)


def _format_reward(amount: Any, symbol: str) -> str:
    """Human-friendly reward, e.g. '1,000 USDC'; never invents a value."""
    if amount is None:
        return "not published"
    try:
        number = float(amount)
    except (TypeError, ValueError):
        return f"{amount} {symbol}".strip()
    if number.is_integer():
        text = f"{int(number):,}"
    else:
        text = f"{number:,.2f}".rstrip("0").rstrip(".")
    return f"{text} {symbol}".strip()


def _bounty_rows(bounties: list[dict]) -> list[list]:
    rows = []
    for b in bounties:
        reward = b.get("remaining_amount")
        if reward is None:
            reward = b.get("reward_amount")
        rows.append(
            [
                b["id"],
                (b.get("title") or "")[:60],
                _format_reward(reward, b.get("reward_symbol", "")),
                (b.get("deadline") or "-")[:10],
                ", ".join(b.get("tags", []))[:30],
                "open" if b.get("is_open") else "closed",
            ]
        )
    return rows


@app.command("list")
def list_cmd(
    page: int = typer.Option(1, "--page", min=1),
    limit: int = typer.Option(15, "--limit", min=1, max=15),
    no_cache: bool = typer.Option(False, "--no-cache", help="Do not store results locally."),
) -> None:
    """List bounties from the Gibwork public listing."""
    try:
        data = BountyService(get_services()).list_remote(page=page, limit=limit, cache=not no_cache)
    except Exception as exc:  # noqa: BLE001 - mapped below
        from bountypilot.cli import handle_error

        handle_error(exc)
        return
    if get_context().json_mode:
        emit_json(data)
        return
    emit_table(
        data["bounties"],
        f"Gibwork bounties (page {data['page']}/{data['last_page']}, total {data['total']})",
        ["ID", "Title", "Reward", "Deadline", "Tags", "State"],
        _bounty_rows(data["bounties"]),
        empty_state="No bounties returned for this page.",
    )
    if data.get("note"):
        echo(f"[yellow]Note: {data['note']}[/yellow]")
    echo(f"[dim]Source: {data['source']} - retrieved in {data['retrieval_seconds']}s[/dim]")


@app.command("search")
def search(
    keywords: str = typer.Argument(..., help="Search keywords."),
    page: int = typer.Option(1, "--page", min=1),
    limit: int = typer.Option(15, "--limit", min=1, max=15),
) -> None:
    """Search the Gibwork listing server-side by keywords."""
    try:
        data = BountyService(get_services()).list_remote(page=page, limit=limit, search=keywords)
    except Exception as exc:  # noqa: BLE001 - mapped below
        from bountypilot.cli import handle_error

        handle_error(exc)
        return
    if get_context().json_mode:
        emit_json(data)
        return
    emit_table(
        data["bounties"],
        f"Search results for {keywords!r} (total {data['total']})",
        ["ID", "Title", "Reward", "Deadline", "Tags", "State"],
        _bounty_rows(data["bounties"]),
        empty_state=f"No bounties matched {keywords!r}. Try different keywords.",
    )
    if data.get("note"):
        echo(f"[yellow]Note: {data['note']}[/yellow]")


@app.command("show")
def show(
    bounty_id: str = typer.Argument(..., help="Bounty UUID."),
    refresh: bool = typer.Option(False, "--refresh", help="Re-fetch from Gibwork even if cached."),
) -> None:
    """Show one bounty (cached snapshot first; live data with --refresh)."""
    try:
        data = BountyService(get_services()).show(bounty_id, refresh=refresh)
    except Exception as exc:  # noqa: BLE001 - mapped below
        from bountypilot.cli import handle_error

        handle_error(exc)
        return
    if get_context().json_mode:
        emit_json(data)
        return
    b = data["bounty"]
    echo(f"[bold]{escape_markup(b['title'])}[/bold]")
    detail("ID", b["id"])
    detail("URL", b.get("url"))
    reward = b.get("remaining_amount") if b.get("remaining_amount") is not None else b.get("reward_amount")
    detail("Reward", _format_reward(reward, b.get("reward_symbol", "")))
    detail("Deadline", b.get("deadline") or "not published")
    detail("Status", b.get("status") or "unknown")
    detail("Open", b.get("is_open"))
    detail("Poster", b.get("poster_username") or "unknown")
    detail("Tags", ", ".join(b.get("tags", [])) or "(none)")
    detail("Source", f"{data['source']} (retrieved {b.get('retrieved_at')})")
    echo()
    content = (b.get("content") or "").strip()
    if content:
        echo(escape_markup(content))
    else:
        echo("[dim]No description published for this bounty.[/dim]")


@app.command("filter")
def filter_cmd(
    min_reward: str = typer.Option("", "--min-reward"),
    max_reward: str = typer.Option("", "--max-reward"),
    tag: str = typer.Option("", "--tag"),
) -> None:
    """Filter locally cached bounties on fields that actually exist."""
    from bountypilot.cli import handle_error

    services = get_services()
    try:
        from bountypilot.core import validation

        min_r = validation.optional_int(min_reward, "min-reward")
        max_r = validation.optional_int(max_reward, "max-reward")
    except Exception as exc:
        handle_error(exc)
        return
    rows = BountyService(services).filter_local(min_reward=min_r, max_reward=max_r, tag=tag or None)
    if get_context().json_mode:
        emit_json(rows)
        return
    emit_table(
        rows,
        "Filtered bounties (local cache)",
        ["ID", "Title", "Reward", "Deadline", "Tags", "State"],
        _bounty_rows(rows),
        empty_state="No cached bounties match. Run 'bountypilot bounty list' first.",
    )


@app.command("recommend")
def recommend(
    top: int = typer.Option(5, "--top", min=1, max=15),
    min_reward: str = typer.Option("", "--min-reward"),
) -> None:
    """Rank bounties with a transparent score built from real fields only."""
    from bountypilot.cli import handle_error

    try:
        from bountypilot.core import validation

        min_r = validation.optional_int(min_reward, "min-reward")
        data = BountyService(get_services()).recommend(top=top, min_reward=min_r)
    except Exception as exc:
        handle_error(exc)
        return
    if get_context().json_mode:
        emit_json(data)
        return
    echo(f"Criteria: {data['criteria']}")
    echo()
    rows = []
    for rec in data["recommendations"]:
        breakdown = rec["score_breakdown"]
        rows.append(
            [
                rec["bounty_id"],
                rec["title"][:50],
                rec["score"],
                _format_reward(rec["reward"], rec["reward_symbol"]),
                rec["deadline_note"],
                f"reward {breakdown['reward_points']} + open {breakdown['open_bonus']} "
                f"+ pool {breakdown['pool_points']} {breakdown['urgency_penalty']}",
            ]
        )
    emit_table(
        rows,
        "Recommended bounties (estimates)",
        ["ID", "Title", "Score", "Reward", "Deadline", "Breakdown"],
        rows,
        empty_state="No bounties available to rank.",
    )


@app.command("compare")
def compare(id1: str = typer.Argument(...), id2: str = typer.Argument(...)) -> None:
    """Compare two bounties field by field."""
    from bountypilot.cli import handle_error

    try:
        data = BountyService(get_services()).compare(id1, id2)
    except Exception as exc:
        handle_error(exc)
        return
    if get_context().json_mode:
        emit_json(data)
        return
    for b in data["bounties"]:
        echo(f"[bold]{escape_markup(b['title'])}[/bold] ({b['id']})")
        detail(
            "Reward",
            _format_reward(
                b.get("remaining_amount") if b.get("remaining_amount") is not None else b.get("reward_amount"),
                b.get("reward_symbol", ""),
            ),
        )
        detail("Deadline", b.get("deadline") or "-")
        detail("Open", b.get("is_open"))
        echo()
    if data["differences"]:
        rows = [[d["field"], str(d["id1"]), str(d["id2"])] for d in data["differences"]]
        emit_table(rows, "Differences", ["Field", "Bounty 1", "Bounty 2"], rows)
    else:
        echo("The two bounties are equal on all compared fields.")

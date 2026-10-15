"""Integration tests through the full CLI with the fake Gibwork client."""

from __future__ import annotations

import json

from tests.conftest import HACKATHON_BOUNTY_ID


def test_help_lists_all_families(runner, app):
    result = runner.invoke(app, [])
    # click >= 8.2 exits 2 (invalid usage: no command given) while still
    # printing the full help; exit code 0 is accepted for older click.
    assert result.exit_code in (0, 2)
    assert "Usage:" in result.output
    for family in (
        "init",
        "doctor",
        "config",
        "gibwork",
        "bounty",
        "analyze",
        "plan",
        "checklist",
        "track",
        "project",
        "docs",
        "evidence",
        "report",
        "submission",
        "reminders",
        "watch",
        "interactive",
    ):
        assert family in result.output


def test_version(runner, app):
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.output.startswith("bountypilot ")


def test_init_is_idempotent(runner, app, args_factory):
    first = runner.invoke(app, args_factory("init", json_mode=True))
    assert first.exit_code == 0
    payload = json.loads(first.output)
    assert payload["database_created"] is True
    second = runner.invoke(app, args_factory("init", json_mode=True))
    assert second.exit_code == 0
    assert json.loads(second.output)["database_created"] is False


def test_config_show_redacts_secrets(runner, app, args_factory):
    runner.invoke(app, args_factory("config", "set", "GIBWORK_API_KEY", "hunter2-secret"))
    result = runner.invoke(app, args_factory("config", "show", json_mode=True))
    assert result.exit_code == 0
    assert "hunter2-secret" not in result.output
    assert "[REDACTED]" in result.output


def test_config_set_rejects_unknown_key(runner, app, args_factory):
    result = runner.invoke(app, args_factory("config", "set", "NOT_A_KEY", "x", json_mode=True))
    assert result.exit_code == 3  # configuration error
    assert "Unknown configuration key" in result.output


def test_gibwork_test_with_fake_client(runner, app, args_factory):
    result = runner.invoke(app, args_factory("gibwork", "test", json_mode=True))
    assert result.exit_code == 0
    assert json.loads(result.output)["reachable"] is True


def test_gibwork_test_unavailable_exit_code(runner, app, args_factory, fake_client):
    fake_client.fail = True
    result = runner.invoke(app, args_factory("gibwork", "test", json_mode=True))
    assert result.exit_code == 5  # service unavailable


def test_gibwork_capabilities_lists_unsupported(runner, app, args_factory):
    result = runner.invoke(app, args_factory("gibwork", "capabilities", json_mode=True))
    payload = json.loads(result.output)
    assert "bounty creation" in payload["operations"]
    assert "Unsupported by the provider" in payload["operations"]["bounty creation"]


def test_full_workflow(runner, app, args_factory):
    """init -> list -> show -> analyze -> track -> report -> submission check."""
    assert runner.invoke(app, args_factory("init", json_mode=True)).exit_code == 0

    listing = runner.invoke(app, args_factory("bounty", "list", json_mode=True))
    assert listing.exit_code == 0
    assert len(json.loads(listing.output)["bounties"]) == 2

    show = runner.invoke(app, args_factory("bounty", "show", HACKATHON_BOUNTY_ID, json_mode=True))
    assert show.exit_code == 0
    assert json.loads(show.output)["bounty"]["title"].startswith("Gibwork")

    analysis = runner.invoke(app, args_factory("analyze", HACKATHON_BOUNTY_ID, json_mode=True))
    assert analysis.exit_code == 0
    payload = json.loads(analysis.output)
    assert payload["analysis"]["requirements"]
    assert payload["analysis"]["origin"] == "ai_estimate"

    focus = runner.invoke(app, args_factory("analyze", "skills", HACKATHON_BOUNTY_ID, json_mode=True))
    assert focus.exit_code == 0
    assert json.loads(focus.output)["analysis"]["skills"]

    plan = runner.invoke(app, args_factory("plan", HACKATHON_BOUNTY_ID, json_mode=True))
    assert plan.exit_code == 0
    assert json.loads(plan.output)["plan"]["origin"] == "ai_estimate"

    track = runner.invoke(app, args_factory("track", "add", HACKATHON_BOUNTY_ID, json_mode=True))
    assert track.exit_code == 0
    bad_transition = runner.invoke(
        app, args_factory("track", "status", HACKATHON_BOUNTY_ID, "completed", json_mode=True)
    )
    assert bad_transition.exit_code == 6  # validation failure
    good_transition = runner.invoke(
        app, args_factory("track", "status", HACKATHON_BOUNTY_ID, "evaluating", json_mode=True)
    )
    assert good_transition.exit_code == 0

    report = runner.invoke(app, args_factory("report", "generate", HACKATHON_BOUNTY_ID, json_mode=True))
    assert report.exit_code == 0
    paths = json.loads(report.output)
    assert paths["markdown_path"].endswith(".md")

    check = runner.invoke(
        app,
        args_factory(
            "submission",
            "check",
            HACKATHON_BOUNTY_ID,
            "--repo-url",
            "https://github.com/example/bountypilot-ai",
            json_mode=True,
        ),
    )
    assert check.exit_code == 0
    payload = json.loads(check.output)
    assert payload["ready"] is False  # honest: most items are missing in a clean run
    assert payload["owner_only_manual_tasks"]


def test_bounty_show_invalid_id_exit_6(runner, app, args_factory):
    result = runner.invoke(app, args_factory("bounty", "show", "garbage", json_mode=True))
    assert result.exit_code == 6


def test_bounty_filter(runner, app, args_factory):
    runner.invoke(app, args_factory("bounty", "list", json_mode=True))
    result = runner.invoke(app, args_factory("bounty", "filter", "--min-reward", "500", json_mode=True))
    assert result.exit_code == 0
    rows = json.loads(result.output)
    assert all((b["remaining_amount"] or 0) >= 500 for b in rows)


def test_track_export_import_roundtrip(runner, app, args_factory, tmp_path):
    runner.invoke(app, args_factory("bounty", "list", json_mode=True))
    runner.invoke(app, args_factory("track", "add", HACKATHON_BOUNTY_ID, json_mode=True))
    export_path = tmp_path / "export.json"
    result = runner.invoke(app, args_factory("track", "export", str(export_path), json_mode=True))
    assert result.exit_code == 0
    data = json.loads(export_path.read_text())
    assert data[0]["bounty_id"] == HACKATHON_BOUNTY_ID

    # Import into the same db without overwrite -> skipped.
    imp = runner.invoke(app, args_factory("track", "import", str(export_path), json_mode=True))
    assert imp.exit_code == 0


def test_json_output_is_valid_json(runner, app, args_factory):
    result = runner.invoke(app, args_factory("gibwork", "status", json_mode=True))
    json.loads(result.output)  # must not raise

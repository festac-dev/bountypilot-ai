"""End-to-end workflow tests with the fake Gibwork client (no network)."""

from __future__ import annotations

import json

from tests.conftest import HACKATHON_BOUNTY_ID


def test_evidence_capture_and_list(runner, app, args_factory):
    result = runner.invoke(
        app,
        args_factory(
            "evidence",
            "capture",
            "sample test output",
            "--kind",
            "test_summary",
            "--bounty",
            HACKATHON_BOUNTY_ID,
            json_mode=True,
        ),
        input="pytest: 5 passed in 0.1s\n",
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["sha256"].startswith("sha256:")

    listing = runner.invoke(app, args_factory("evidence", "list", json_mode=True))
    rows = json.loads(listing.output)
    assert any(e["kind"] == "test_summary" for e in rows)


def test_evidence_redacts_secrets(runner, app, args_factory, tmp_path, data_dir):
    result = runner.invoke(
        app,
        args_factory(
            "evidence",
            "capture",
            "accidental secret",
            "--kind",
            "log",
            json_mode=True,
        ),
        input="config api_key=supersecret-token-value\n",
    )
    assert result.exit_code == 0
    stored = json.loads(result.output)["path"]
    content = open(stored).read()
    assert "supersecret-token-value" not in content


def test_docs_generation(runner, app, args_factory):
    runner.invoke(app, args_factory("bounty", "list", json_mode=True))
    readme = runner.invoke(app, args_factory("docs", "readme", HACKATHON_BOUNTY_ID, json_mode=True))
    assert readme.exit_code == 0
    path = json.loads(readme.output)["path"]
    content = open(path).read()
    assert "Use Case / Value / Gibwork Toolset Used" in content

    setup = runner.invoke(app, args_factory("docs", "setup", HACKATHON_BOUNTY_ID, json_mode=True))
    assert setup.exit_code == 0

    acceptance = runner.invoke(app, args_factory("docs", "acceptance", HACKATHON_BOUNTY_ID, json_mode=True))
    assert acceptance.exit_code == 0


def test_submissions_package_creation(runner, app, args_factory, tmp_path):
    runner.invoke(app, args_factory("bounty", "list", json_mode=True))
    out = tmp_path / "packages"
    result = runner.invoke(
        app,
        args_factory("submission", "package", HACKATHON_BOUNTY_ID, "--out", str(out), json_mode=True),
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["archive"].endswith(".zip")


def test_watch_poll_detects_no_changes(runner, app, args_factory):
    runner.invoke(app, args_factory("bounty", "list", json_mode=True))
    result = runner.invoke(app, args_factory("watch", HACKATHON_BOUNTY_ID, json_mode=True))
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["polls"] == []

    listing = runner.invoke(app, args_factory("watch", "list", json_mode=True))
    rows = json.loads(listing.output)
    assert rows[0]["bounty_id"] == HACKATHON_BOUNTY_ID
    assert rows[0]["mode"] == "periodic polling (not real-time)"


def test_reminders_add_list_remove(runner, app, args_factory):
    runner.invoke(app, args_factory("bounty", "list", json_mode=True))
    added = runner.invoke(app, args_factory("reminders", "add", HACKATHON_BOUNTY_ID, json_mode=True))
    assert added.exit_code == 0
    rows = json.loads(runner.invoke(app, args_factory("reminders", "list", json_mode=True)).output)
    assert len(rows) == 1
    removed = runner.invoke(app, args_factory("reminders", "remove", "1", json_mode=True))
    assert removed.exit_code == 0
    rows = json.loads(runner.invoke(app, args_factory("reminders", "list", json_mode=True)).output)
    assert rows == []


def test_doctor_reports_checks(runner, app, args_factory):
    result = runner.invoke(app, args_factory("doctor", json_mode=True))
    assert result.exit_code == 0
    payload = json.loads(result.output)
    names = {c["name"] for c in payload["checks"]}
    assert {"python", "bountypilot", "requests", "database", "data_directory", "gibwork"} <= names
    assert payload["all_ok"] is True


def test_project_audit_finds_issues(runner, app, args_factory, tmp_path):
    bare = tmp_path / "bare"
    bare.mkdir()
    result = runner.invoke(app, args_factory("project", "audit", str(bare), json_mode=True))
    payload = json.loads(result.output)
    findings = " ".join(f["finding"] for f in payload["findings"])
    assert "README" in findings
    assert "tests" in findings


def test_project_audit_does_not_flag_itself(runner, app, args_factory, tmp_path):
    """A file containing only the audit's own warning text must not be flagged."""
    (tmp_path / "report.py").write_text('print("Possible eval() use at somewhere.py:1")\n')
    result = runner.invoke(app, args_factory("project", "audit", str(tmp_path), json_mode=True))
    payload = json.loads(result.output)
    findings = " ".join(f["finding"] for f in payload["findings"])
    assert "report.py" not in findings
    (tmp_path / "danger.py").write_text("value = eval(user_input)\n")
    result = runner.invoke(app, args_factory("project", "audit", str(tmp_path), json_mode=True))
    payload = json.loads(result.output)
    findings = " ".join(f["finding"] for f in payload["findings"])
    assert "danger.py" in findings


def test_project_inspect(runner, app, args_factory, tmp_path):
    result = runner.invoke(app, args_factory("project", "inspect", str(tmp_path), json_mode=True))
    payload = json.loads(result.output)
    assert payload["path"] == str(tmp_path.resolve())

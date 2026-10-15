"""Unit tests: terminal output safety (rich markup handling)."""

from __future__ import annotations

import io

from bountypilot import output as out


def _capture_console(monkeypatch):
    buffer = io.StringIO()
    monkeypatch.setattr(out._console, "file", buffer)
    out.set_json_mode(False)
    return buffer


def test_escape_markup_neutralises_style_tags():
    assert out.escape_markup("[bold]x[/bold]") == r"\[bold]x\[/bold]"


def test_table_cell_with_closing_tag_does_not_crash(monkeypatch):
    _capture_console(monkeypatch)
    out.emit_table(
        {"id": 1},
        "Test",
        ["Title"],
        [["Delete [/tmp] files"]],
    )
    # No exception: the untrusted cell renders literally.


def test_table_cell_brackets_render_literally(monkeypatch):
    buffer = _capture_console(monkeypatch)
    out.emit_table({"id": 1}, "Test", ["Title"], [["Fix [bug]"]])
    assert "Fix [bug]" in buffer.getvalue()


def test_detail_value_brackets_render_literally(monkeypatch):
    buffer = _capture_console(monkeypatch)
    out.detail("Evidence", "/project/[weird]/path")
    assert "/project/[weird]/path" in buffer.getvalue()


def test_estimate_label_survives_markup(monkeypatch):
    buffer = _capture_console(monkeypatch)
    out.detail("Difficulty", "low [estimate]")
    assert "low [estimate]" in buffer.getvalue()


def test_bracketed_evidence_line_renders_literally(monkeypatch):
    buffer = _capture_console(monkeypatch)
    # Mirrors the submission-check line: a path as evidence must not be parsed
    # as a closing style tag ("[/path]" crashed before the fix).
    evidence = "/vercel/sandbox/repos/project"
    out.echo(f"  [green]PASS[/green]  Source code  \\[{out.escape_markup(evidence)}]")
    assert f"Source code  [{evidence}]" in buffer.getvalue()

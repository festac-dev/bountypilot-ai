"""Health checks for the Gibwork integration and local dependencies."""

from __future__ import annotations

import sqlite3
import sys
from typing import Any

import requests

from bountypilot import __version__
from bountypilot.integrations.gibwork.client import GibworkClient
from bountypilot.settings import Settings


def python_version_ok() -> tuple[bool, str]:
    version = sys.version_info
    ok = version >= (3, 11)
    return ok, f"Python {version.major}.{version.minor}.{version.micro}"


def requests_available() -> tuple[bool, str]:
    return True, f"requests {requests.__version__}"


def database_ok(settings: Settings) -> tuple[bool, str]:

    path = settings.database_path
    if not path.exists():
        return True, f"database not created yet ({path})"
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
        try:
            conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
        finally:
            conn.close()
        return True, f"database readable ({path})"
    except sqlite3.Error as exc:
        return False, f"database problem: {exc}"


def data_directory_writable(settings: Settings) -> tuple[bool, str]:
    directory = settings.data_directory
    if not directory.exists():
        return True, f"{directory} (not created yet)"
    probe = directory / ".write-probe"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True, f"{directory} writable"
    except OSError as exc:
        return False, f"{directory} not writable: {exc}"


def gibwork_health(client: GibworkClient) -> dict[str, Any]:
    return client.health()


def doctor_report(settings: Settings, client: GibworkClient) -> dict[str, Any]:
    """Collect every diagnostic in one structured report."""
    py_ok, py_msg = python_version_ok()
    req_ok, req_msg = requests_available()
    db_ok, db_msg = database_ok(settings)
    dir_ok, dir_msg = data_directory_writable(settings)
    checks = [
        {"name": "python", "ok": py_ok, "detail": py_msg},
        {"name": "bountypilot", "ok": True, "detail": f"version {__version__}"},
        {"name": "requests", "ok": req_ok, "detail": req_msg},
        {"name": "database", "ok": db_ok, "detail": db_msg},
        {"name": "data_directory", "ok": dir_ok, "detail": dir_msg},
    ]
    health = gibwork_health(client)
    checks.append(
        {
            "name": "gibwork",
            "ok": bool(health.get("reachable")),
            "detail": ("reachable" if health.get("reachable") else f"unreachable: {health.get('error')}"),
        }
    )
    return {"checks": checks, "gibwork": health, "all_ok": all(c["ok"] for c in checks)}

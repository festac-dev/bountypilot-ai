"""Entry point for the bountypilot console script."""

from __future__ import annotations

import sys


def app_entry() -> None:
    try:
        from bountypilot.cli import app

        app()
    except SystemExit as exc:
        code = exc.code
        if isinstance(code, bool):
            code = 0 if not code else 1
        if code is None or not isinstance(code, int):
            code = 0
        sys.exit(code)


if __name__ == "__main__":  # pragma: no cover
    app_entry()

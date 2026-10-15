#!/usr/bin/env bash
# Full local quality workflow for BountyPilot AI.
set -euo pipefail
cd "$(dirname "$0")/.."

PY=${PYTHON:-python3}

echo "==> Creating/refreshing isolated virtualenv (.venv)"
if [ ! -d .venv ]; then
  "$PY" -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip setuptools >/dev/null
echo "==> Installing package with dev extras"
.venv/bin/python -m pip install -e ".[dev]" >/dev/null

echo "==> Metadata sanity"
.venv/bin/bountypilot --version

echo "==> Lint (ruff check)"
.venv/bin/ruff check src tests

echo "==> Format (ruff format --check)"
.venv/bin/ruff format --check src tests

echo "==> Types (mypy)"
.venv/bin/mypy src/bountypilot

echo "==> Tests (offline)"
.venv/bin/python -m pytest tests -q

echo "==> Opt-in live Gibwork checks"
BOUNTYPILOT_LIVE_TESTS=1 .venv/bin/python -m pytest tests/integration/test_live_gibwork.py -q || {
  echo "!! live checks failed (network may be unavailable) - offline results above still count"
}

echo "==> All quality gates finished."

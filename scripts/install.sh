#!/usr/bin/env bash
# Clean-environment install verification for BountyPilot AI (Linux/Termux).
set -euo pipefail
cd "$(dirname "$0")/.."

PY=${PYTHON:-python3}
VENV_DIR=${1:-/tmp/bountypilot-install-check-$$}

echo "==> Checking Python version (3.11+ required)"
if ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo "ERROR: BountyPilot AI requires Python 3.11+; '$PY' is $("$PY" -V 2>&1 | cut -d' ' -f2)." >&2
  echo "Set PYTHON=/path/to/python3.11 or install Python 3.11+ (e.g. 'pkg install python' on Termux) and retry." >&2
  exit 1
fi

echo "==> Creating clean venv at $VENV_DIR"
"$PY" -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip >/dev/null

echo "==> Installing from the repository"
"$VENV_DIR/bin/python" -m pip install .

echo "==> Verifying entry points"
"$VENV_DIR/bin/bountypilot" --version
"$VENV_DIR/bin/bountypilot" --help >/dev/null && echo "help OK"

echo "==> Isolated smoke run"
export BOUNTYPILOT_DATA_DIRECTORY="$VENV_DIR-data"
"$VENV_DIR/bin/bountypilot" init
"$VENV_DIR/bin/bountypilot" doctor

echo "==> Install check finished. Data dir: $BOUNTYPILOT_DATA_DIRECTORY"
echo "    Remove with: rm -rf \"$VENV_DIR\" \"$BOUNTYPILOT_DATA_DIRECTORY\""

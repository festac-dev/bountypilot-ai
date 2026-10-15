#!/usr/bin/env bash
# Pre-release checklist for BountyPilot AI. Run before tagging a release.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> 1. Full quality workflow"
bash scripts/dev-check.sh

echo "==> 2. Build distributions"
PY=${PYTHON:-python3}
"$PY" -m pip install --quiet build 2>/dev/null || true
"$PY" -m build

echo "==> 3. Install the built wheel into a clean venv and smoke it"
bash scripts/install.sh /tmp/bountypilot-release-check-$$

echo "==> 4. Reminders"
echo "    - Update CHANGELOG.md for the new version."
echo "    - Verify docs/IMPLEMENTATION_STATUS.md reflects reality."
echo "    - Never publish to a registry without explicit authorization."
echo "Release check finished."

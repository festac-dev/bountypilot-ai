# Contributing to BountyPilot AI

Thanks for considering a contribution.

## Ground rules

- Terminal only: no web server, dashboard or browser UI will be accepted.
- Real behaviour only: no "coming soon" stubs, no fabricated results.
- Honesty about capabilities: label generated estimates, never present mocked
  responses as live integrations.
- Secrets: never commit, log, print or store credentials in bounty records.

## Development workflow

1. Fork/branch from `main`.
2. Set up: `bash scripts/dev-check.sh` (creates `.venv`, installs, lints, tests).
3. Make focused changes; extend the architecture (commands -> services ->
   repositories/integrations) rather than bypassing it.
4. Add or update tests for behaviour changes; keep the offline suite fast and
   hermetic (use the fake Gibwork client in `tests/conftest.py`).
5. Run `make dev-check` before opening a pull request.

## Commit style

Short imperative subject lines ("Add watch polling change records"), body for
context. Keep diffs surgical.

## Reporting issues

Include the command, the exact output (with secrets removed), the platform
(Linux/Termux/macOS) and the Python version. `bountypilot doctor --json` is a
good starting point.

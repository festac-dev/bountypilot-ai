# Deployment

BountyPilot is a local terminal tool: there is no server, no hosted component,
and no mandatory container. Deployment means installing and verifying on the
target machine.

## Verified deployment path

1. Clean install: `bash scripts/install.sh` (fresh venv, install, `init`,
   `doctor`). Verified on Python 3.11 during development; CI matrix covers
   3.11/3.12.
2. Configuration: `bountypilot config set ...` or environment variables.
3. Dependency checks: `bountypilot doctor`.
4. Gibwork verification: `bountypilot gibwork test`.
5. Database initialization: `bountypilot init` (idempotent).
6. Basic workflow: `bountypilot bounty list` -> `bounty show <id>` ->
   `track add <id>`.
7. Tests: `make test` (offline), `make test-live` (opt-in).

## Upgrade

```bash
git pull && .venv/bin/python -m pip install -e .
bountypilot init        # applies pending migrations
bountypilot doctor
```

## Backup and recovery

- Everything lives under the data directory (default
  `~/.local/share/bountypilot`): `config.json`, `bountypilot.db`,
  `evidence/`, `exports/`.
- Backup: stop using the tool, copy the whole directory (or use
  `bountypilot track export` for tracking data).
- Recovery: restore the directory, run `bountypilot init`, then `doctor`.
- Rollback: `git checkout <previous-tag>`, reinstall, restore the DB backup.

## Containers (optional, not required)

No Dockerfile ships in this version: the reliable local install route
(venv + pip) is mandatory and sufficient for Termux/Linux. Container images
would have to run as non-root with a persistent volume for the data directory
and no embedded secrets - only add one if a real need appears.

## Background execution

BountyPilot does not run in the background. For reminder checks, schedule
them yourself:

```bash
# cron example: 09:00 daily
0 9 * * * ~/.venv/bin/bountypilot reminders list >> ~/.bountypilot-reminders.log 2>&1
```

On Termux, use Termux:Boot + the Job Scheduler or `cron` from `pkg install cronie`.

Items labelled "unverified" above (e.g. Termux-specific shells) were not run
in this environment; see docs/IMPLEMENTATION_STATUS.md.

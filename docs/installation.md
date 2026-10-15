# Installation

## Requirements

- Python 3.11+
- pip and venv
- No GPU, no database server, no Docker, no AI key required

## Linux / macOS (general)

```bash
git clone https://github.com/festac-dev/bountypilot-ai
cd bountypilot-ai
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .     # CLI only (runtime dependencies)
.venv/bin/bountypilot --help
.venv/bin/bountypilot --version
```

Or run the verification script:

```bash
bash scripts/install.sh    # clean-venv install + init + doctor
```

Note: on Debian/Ubuntu the bare system `pip install -e .` fails with
`error: externally-managed-environment` (PEP 668). That is expected - always
install into the venv as shown above (never `--break-system-packages`).

## Termux (Android)

```bash
pkg update
pkg install python git
python -m ensurepip --upgrade     # if pip is missing
git clone https://github.com/festac-dev/bountypilot-ai
cd bountypilot-ai
python -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
```

Notes:

- BountyPilot deliberately avoids heavy native wheels: the runtime
  dependencies are `typer`, `click`, `rich`, `requests`, so a plain
  `pip install -e .` works everywhere, including Termux. The dev tooling
  (`pytest`, `ruff`, `mypy`) lives in the `[dev]` extra. On Termux, `ruff`
  has no Android wheel (building it runs out of memory), so use
  `pkg install ruff` and `pip install pytest mypy types-requests` instead.
- If `chmod` is unsupported on shared storage, BountyPilot degrades
  gracefully (permissions are best-effort); prefer storing data under the
  app-private home directory.

## First run

```bash
bountypilot init       # creates data directory, database, config (idempotent)
bountypilot doctor     # verifies Python, packages, database, Gibwork reachability
```

## Upgrade

```bash
git pull
.venv/bin/python -m pip install -e .
bountypilot init       # applies any pending database migrations
```

## Rollback

The database schema migrates forward only. To roll back, reinstall the
previous version from git (`git checkout <tag>`) and restore a database backup
(see docs/deployment.md).

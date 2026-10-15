# Troubleshooting

## Installation and CLI startup

### `pip install -e .` refuses: "error: externally-managed-environment"

You ran the **system** pip on a PEP 668 managed distro (Debian/Ubuntu; the
message names `python3 -m venv` and `pipx`). System-wide installs are blocked
by the OS, not by BountyPilot. Do not use `--break-system-packages`; create
and use the venv the installation guide describes:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
bountypilot init && bountypilot doctor
```

Without activating: `.venv/bin/python -m pip install -e .` then call the CLI
as `.venv/bin/bountypilot`. Or run `bash scripts/install.sh`, which creates
its own venv and smoke-tests it.

### `bash: bountypilot: command not found`

The venv is active but the package was never installed into it (or the
install failed partway). From the repo root:

```bash
python -m pip install --upgrade pip
python -m pip install -e .
hash -r            # clear bash's stale command cache, then retry
```

The venv must be Python 3.11+ (`python --version`); the install fails fast
below that with an actionable message. Alternatively
`bash scripts/install.sh` creates its own `.venv` and smoke-tests the result.

### `source .venv/bin/bountypilot` → bizarre errors

`source` executes files as **shell** scripts, but `.venv/bin/bountypilot` is
a Python console script - bash tries to interpret Python code. Symptoms
include `import: unable to open X server` (ImageMagick's `import` being
invoked) and `syntax error near unexpected token '('`. `source` is only for
shell scripts like `source .venv/bin/activate`. Run the command directly:

```bash
bountypilot init
# or without activating the venv:
.venv/bin/bountypilot doctor
```

### `ModuleNotFoundError: No module named 'typer'` (or `click`, `rich`, `requests`)

A runtime dependency is missing, which means the editable install never
completed in that environment. Re-run `python -m pip install -e .` and read
its output; if the install itself errors, fix that first (most common cause:
a Python < 3.11 interpreter - see the next entry).

### `make: ruff: No such file or directory`, `pytest: command not found`, `ModuleNotFoundError ... conftest.py: from typer.testing import CliRunner`

The dev tooling is not part of the base install. On Linux/macOS:

```bash
python -m pip install -e ".[dev]"
make test          # offline suite; no network, no credentials
make lint && make format && make typecheck
```

On Termux use `pkg install ruff` and
`python -m pip install pytest mypy types-requests` instead (see the next
entry).

### Termux: `Building wheel for ruff` runs for 30+ minutes, then `rustc-LLVM ERROR: out of memory`

`ruff` has no Android wheel, so pip compiles it from Rust source with
fat LTO, which exceeds phone RAM and never finishes. Press `Ctrl+C`, then:

```bash
pkg install ruff
python -m pip install -e .
python -m pip install pytest mypy types-requests
```

`pip install -e .` only needs the four runtime dependencies. Avoid
`pip install -e ".[dev]"` on Termux. Run the linter with `ruff check .`
(the Termux binary is on your `PATH`, outside the venv).

### Install refuses: "requires a different Python: 3.9 not in '>=3.11'"

The package requires Python 3.11+. Recreate the venv with a compliant
interpreter (`python3.12 -m venv .venv`), or on Termux `pkg install python`.

## `gibwork test` says unreachable

- Check connectivity: `curl -s https://api.gib.work/explore?page=1 | head`.
- BountyPilot automatically fails over between the two documented hosts
  (`api.gib.work` / `api2.gib.work`) on connection errors, timeouts, and 5xx;
  the active host is shown by `gibwork version` and the Failover line of
  `gibwork status`.
- The `api2.gib.work` host rejects datacenter IPs (HTTP 403). A 403 is an
  access restriction, not unreachability, so BountyPilot reports it as an
  authentication error instead of switching hosts; use
  `GIBWORK_BASE_URL=https://api.gib.work` or a network the API accepts.
- Corporate proxies may require `HTTPS_PROXY` to be set.

## `gibwork status` shows "Authentication required"

Expected without credentials. The public read API works unauthenticated for
page 1 of the listing (limit <= 15). Deep pagination (page > 1) returns HTTP
401; BountyPilot degrades gracefully with an explanatory note instead of
failing. In `official_cli` mode it means the official Gibwork CLI has no
wallet configured. These are documented provider behaviours, not bugs.

## I set GIBWORK_API_KEY and get "Configured but rejected"

No documented API-key authentication exists for the public endpoints.
BountyPilot retries unauthenticated and reports the rejection honestly. Unset
the key unless you have a documented credential flow.

## Database errors

- `DatabaseCorruptionError`: move the file aside and run `bountypilot init`
  to start fresh; re-run `bounty list` to repopulate the cache.
- Restore: stop any process using the DB, copy the `.db` (and `-wal`/`-shm`
  files if present) from your backup into the data directory.

## Permission errors

- The data directory must be writable: check `bountypilot doctor`.
- On Termux shared storage `chmod` may not apply; BountyPilot warns and
  continues. Prefer private app storage.

## JSON output issues

- Always place `--json` before the subcommand: `bountypilot --json bounty list`.
- Debug logs go to stderr; pipe stdout only when consuming JSON.

## Analysis looks shallow

The local provider is a deterministic heuristic parser, not an LLM. Configure
`AI_PROVIDER=remote` with `AI_BASE_URL`/`AI_API_KEY`/`AI_MODEL` for richer
analysis; every remote estimate is still labelled as an estimate.

## Stack traces in output

Only in `--debug` mode. Ordinary errors print one line plus the documented
exit code. If you see a traceback without `--debug`, please open an issue.

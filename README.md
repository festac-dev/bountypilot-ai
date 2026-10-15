# BountyPilot AI

**Discover opportunities. Evaluate bounties. Execute with confidence.**

BountyPilot AI is a terminal-based developer productivity tool for
[Gibwork](https://gib.work) bounties: find real bounties, evaluate them
honestly, plan the work, track progress, gather evidence, and package a
verifiable submission - entirely from the command line.

## Use Case / Value / Gibwork Toolset Used

- **Use case:** a developer wants to find Gibwork bounties worth doing,
  understand what each actually requires, plan the implementation, track
  their own progress, and assemble a submission package with real evidence -
  without opening a browser or spreadsheet.
- **Value:** turns scattered bounty pages into a persistent, validated local
  workflow: cached bounty snapshots, labelled AI/heuristic analysis, a
  lifecycle-aware tracker, timestamped evidence with integrity hashes,
  generated reports, and a submission-readiness check that never pretends a
  manual task was done.
- **Gibwork toolset used:** the **official Gibwork public API** (the
  documented read surface behind the official `@gibwork/sdk`/CLI - see
  [docs/gibwork-integration.md](docs/gibwork-integration.md)), accessed
  through BountyPilot's integration adapter, plus an optional bridge to the
  official `@gibwork/cli` when installed.

## Problem statement

Gibwork bounty evaluation lives in the browser: copy requirements by hand,
guess effort, lose track of deadlines, and assemble submissions ad hoc.
Developers working in terminals (including Android/Termux) need this workflow
where they already work.

## Target users

- Developers hunting Solana/Gibwork bounties.
- Hackathon participants preparing submissions with real evidence.
- Automators/agents that need JSON output from every command.

## Why it is valuable

- Works offline against cached snapshots; live data when you want it.
- Never fabricates: estimates are labelled, manual tasks stay manual, and
  every capability has an explicit status.
- Persistent local state (SQLite) with migrations and safe exports.
- Non-interactive automation friendly: valid JSON everywhere, documented exit
  codes.

## The novel use case

Not a bounty *lister* - a full **evaluation-to-submission pipeline**: retrieve
-> validate -> analyze (labelled estimates) -> plan -> track with a validated
lifecycle -> capture evidence with hashes -> generate reports -> check
submission readiness (evidence-based, attestations unverified) -> package
artifacts with a manifest. A mock is never presented as live data.

## How Gibwork is used

- `bounty list/search/show` read the documented public API.
- `gibwork status/test/auth status` verify the integration honestly.
- Retrieval timestamps and provenance (`origin`, `retrieved_at`) are stored
  with every snapshot.
- Write operations (bounty creation, submissions) require on-chain Solana
  transactions and are deliberately **not implemented** - documented in
  [docs/gibwork-integration.md](docs/gibwork-integration.md).

## Architecture

commands -> services -> repositories / integration adapters. See
[docs/architecture.md](docs/architecture.md).

## Features

- **Discovery:** list, server-side search, detail (cache-first), local filter,
  transparent recommendation scoring, field-by-field comparison.
- **Analysis:** requirement/deliverable extraction, skills detection,
  difficulty and effort *estimates* (always labelled), suggested plans and
  checklists that are never auto-executed.
- **AI:** deterministic local provider (no key, no network) + optional remote
  OpenAI-compatible provider with graceful degradation.
- **Tracking:** Saved -> Evaluating -> Planned -> In progress -> Blocked ->
  Completed / Abandoned with validated transitions; safe export/import.
- **Project tools:** inspect, real test runs, static audit, scaffold from plan.
- **Documentation:** README/setup/acceptance drafts from real stored data.
- **Evidence:** capture with SHA-256 hashes and secret redaction.
- **Reporting:** Markdown + JSON reports from stored facts.
- **Submission:** evidence-based readiness check + package archive with
  manifest; never auto-submits.
- **Reminders & watch:** persistent timezone-aware reminders (OS scheduler for
  background execution); bounded periodic polling with change records.

## Command reference

See [docs/commands.md](docs/commands.md) for the complete inventory with
options and exit codes (0/1/2/3/4/5/6/7).

```text
bountypilot [--version] [--json] [--no-color] [--debug] [--config DIR]
  init | doctor | completion <shell>
  config show | config set <key> <value>
  gibwork status | gibwork auth status | gibwork capabilities | gibwork test | gibwork version
  bounty list | bounty search "<kw>" | bounty show <id> | bounty filter
  bounty recommend | bounty compare <id1> <id2>
  analyze <id> | analyze skills|difficulty|effort|requirements <id>
  plan <id> | checklist <id>
  track add|list|show|status|remove|export|import
  project plan|scaffold|inspect|test|audit|report
  docs readme|setup|acceptance <id>
  evidence capture | evidence list
  report generate <id>
  submission check <id> | submission package <id>
  reminders list | reminders add <id> | reminders remove <row>
  watch <id> | watch list
  interactive
```

## System requirements

## System requirements

- Python 3.11+ (the installer fails fast below 3.11 with an actionable message)
- Linux (primary), Termux/Android (primary), macOS/Windows where practical
- Runtime dependencies: `typer`, `click`, `rich`, `requests` - pure-Python
  wheels with no native builds, so a plain `pip install -e .` works
  everywhere, including Termux.
- Development tooling (optional): `pytest`, `mypy`, `types-requests`,
  `ruff`. Install with `pip install -e ".[dev]"`. `ruff` ships a compiled
  Rust binary; Android has no prebuilt wheel and compiling it from source
  needs more RAM than most phones have. On Termux install it with
  `pkg install ruff` instead (see below).

## Installation

Install the CLI (runtime dependencies only):

### Linux / macOS

```bash
git clone https://github.com/festac-dev/bountypilot-ai
cd bountypilot-ai
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
.venv/bin/bountypilot --version
```

### Termux (Android)

```bash
### Termux (Android)

```bash
pkg update && pkg install python git
python -m ensurepip --upgrade   # if pip missing
git clone https://github.com/festac-dev/bountypilot-ai && cd bountypilot-ai
python -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
.venv/bin/bountypilot --version
```

**Dev tools on Termux** (only needed for `make test` / `make lint` /
`make typecheck`):

```bash
pkg install ruff
.venv/bin/python -m pip install pytest mypy types-requests
```

Do **not** run `pip install -e ".[dev]"` on Termux: pip would try to compile
ruff from source, which takes an hour or more and runs out of memory. Use
the Termux `ruff` package above.

### Development tools (Linux / macOS / Windows)

```bash
.venv/bin/python -m pip install -e ".[dev]"
```
```

With the venv activated, `bountypilot` is on your `PATH`; without
activation, call it as `.venv/bin/bountypilot`. If a freshly installed
command is still "not found", run `hash -r` (bash caches command lookups).

### First run

```bash
bountypilot init      # data directory + database + config (idempotent)
bountypilot doctor    # environment + database + Gibwork checks
```


## Configuration and environment variables

`.env.example` documents every variable; see
[docs/configuration.md](docs/configuration.md) for the precedence rules
(command line > environment > config file > defaults) and the full reference.
Secrets are redacted in all output.

## Authentication

Per the official documentation, BountyPilot's primary path needs **no
authentication** for read access (page 1 of the public listing). There is no
documented API-key flow for the public endpoints; `GIBWORK_API_KEY` is sent if
configured but a rejection is reported honestly and the tool degrades to
unauthenticated reads. Wallet-based writes are out of scope. Details:
[docs/gibwork-integration.md](docs/gibwork-integration.md).

## Usage examples and sample output

```text
$ bountypilot gibwork test
✔ Gibwork is reachable. Public listing shows 8 bounties.

$ bountypilot bounty list
                      Gibwork bounties (page 1/1, total 8)
╭──────────┬─────────────────┬─────────────┬────────────┬──────────────┬───────╮
│ ID       │ Title           │ Reward      │ Deadline   │ Tags         │ State │
├──────────┼─────────────────┼─────────────┼────────────┼──────────────┼───────┤
│ 1052f22d │ Gibwork         │ 1,000 USDC  │ 2026-10-30 │ Development  │ open  │
│          │ Developer       │             │            │              │       │
│          │ Hackathon       │             │            │              │       │
│          │ Bounty          │             │            │              │       │
└──────────┴─────────────────┴─────────────┴────────────┴──────────────┴───────┘
Source: gibwork public listing - retrieved in 0.08s
```

*(Output captured 2026-10-13 against the live public API.)*

```text
$ bountypilot --json gibwork status
{
  "state": "Connected",
  "note": "public API: https://api.gib.work",
  "reachable": true,
  "error": "",
  "auth_state": "unauthenticated",
  "failover_note": ""
}
```

More examples: [docs/demo-script.md](docs/demo-script.md).

## Testing

```bash
make test         # offline suite (102 tests; no network, no credentials)
make test-live    # opt-in live checks against the real public API
make lint && make format && make typecheck
```

See [docs/testing.md](docs/testing.md).

## Development

```bash
bash scripts/dev-check.sh   # venv + install + lint + types + tests + live checks
```

See [docs/development.md](docs/development.md) and
[CONTRIBUTING.md](CONTRIBUTING.md).

## Deployment options

Local install is the deployment (Termux/Linux/macOS). Backup, upgrade,
rollback and scheduler recipes: [docs/deployment.md](docs/deployment.md).

## Security

Read-only integration, secret redaction everywhere, 0600 config files,
0700 data directory, traversal-checked exports, argument-array subprocesses,
bounded retries. `project audit` is a heuristic check, not a scanner.
Details: [docs/security.md](docs/security.md), [SECURITY.md](SECURITY.md).

## Known limitations

- No write operations: creating bounties or submitting solutions requires
  on-chain Solana transactions / an authenticated session - deliberately not
  implemented.
- Unauthenticated pagination covers page 1 of the public listing (limit <= 15);
  deeper pages return HTTP 401 (provider behaviour). BountyPilot degrades
  gracefully: deeper pages return an empty result with an explanatory note.
- `api2.gib.work` rejects some datacenter IPs (403); the default base URL is
  `https://api.gib.work`. BountyPilot fails over automatically between the two
  documented hosts when one is unreachable; a WAF block is reported as an
  access restriction rather than silently switching hosts.
- The local analysis provider is a deterministic heuristic parser; remote AI
  is optional and estimates are always labelled.
- Background reminder execution requires an external scheduler (cron /
  Termux Job Scheduler).
- No Docker image by design; the venv route is the supported path.
- Implemented vs planned vs unsupported status for every feature:
  [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md).

## Troubleshooting

Everything below is a real failure mode with a verified fix. The full page,
including provider-side and database issues, is
[docs/troubleshooting.md](docs/troubleshooting.md).

### `pip install -e .` refuses: `error: externally-managed-environment`

You ran the **system** pip (Debian/Ubuntu and other PEP 668 distros block
system-wide installs - the message names `python3 -m venv` or `pipx` for a
reason). Do **not** use `--break-system-packages`; create the venv the
Installation section describes:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
bountypilot init && bountypilot doctor
```

Without activating, use `.venv/bin/python -m pip install -e .` and call the
CLI as `.venv/bin/bountypilot`. Or let `bash scripts/install.sh` create and
verify the venv for you.

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

### `source .venv/bin/bountypilot` → bizarre errors (`import: unable to open X server`, `syntax error near unexpected token '('`)

`source` executes files as **shell** scripts, but `.venv/bin/bountypilot` is
a Python console script — bash tries to interpret Python code (the
`import:` error is ImageMagick's `import` being invoked). `source` is only
for shell scripts like `source .venv/bin/activate`. Run the command directly:

```bash
bountypilot init
# or without activating the venv:
.venv/bin/bountypilot doctor
```

### `ModuleNotFoundError: No module named 'typer'` (or `click`, `rich`, `requests`)

A runtime dependency is missing, which means the editable install never
completed in that environment. Re-run the install and read its output:

```bash
python -m pip install -e .
```

If `pip install -e .` itself errors, fix that first — everything else depends
on it (see the Python-version entry below for the most common cause).

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

### `pip install` refuses: "requires a different Python: 3.9 not in '>=3.11'"

The package requires Python 3.11+. Check with `python --version`, then either
point the venv at a compliant interpreter
(`python3.12 -m venv .venv`), or on Termux: `pkg install python`. On Termux,
`pkg install python` currently provides 3.11/3.12.

### `gibwork test` says unreachable / `bounty list` exits 4 or 5

- BountyPilot automatically fails over between the two documented hosts
  (`api.gib.work` / `api2.gib.work`) on connection errors, timeouts, and 5xx;
  the active host is shown by `gibwork version` and `gibwork status`.
- A 403 is a WAF access restriction (some datacenter IPs), reported as an
  authentication error rather than silently switching hosts; set
  `GIBWORK_BASE_URL=https://api.gib.work` if needed.
- Corporate proxies may require `HTTPS_PROXY` to be set.

### `gibwork status` shows "Authentication required" / deep pagination returns nothing

Documented provider behaviour, not a bug: the public read API works
unauthenticated for page 1 of the listing (limit <= 15); deeper pages return
HTTP 401, and BountyPilot degrades gracefully with an explanatory note. In
`official_cli` mode it means the official Gibwork CLI has no wallet
configured.

### `I set GIBWORK_API_KEY and get "Configured but rejected"`

No documented API-key authentication exists for the public endpoints.
BountyPilot retries unauthenticated and reports the rejection honestly. Unset
the key unless you have a documented credential flow.

### Stack traces in output

Only in `--debug` mode. Ordinary errors print one line plus the documented
exit code (0/1/2/3/4/5/6/7 - see [docs/commands.md](docs/commands.md)). If
you see a traceback without `--debug`, please open an issue.

### Database or permission errors

- `DatabaseCorruptionError`: move the `.db` file aside and run
  `bountypilot init` to start fresh; `bounty list` repopulates the cache.
- The data directory must be writable - check `bountypilot doctor`. On Termux
  shared storage `chmod` may not apply; BountyPilot warns and continues.
  Prefer private app storage.

## Screenshots

See [Screenshots](./screenshots)

## Demo video 

Demo video available on [YouTube](https://youtu.be/r5egm9h7T50?si=GiY0rUI84uTD5xmV)

## License

[Apache License 2.0](LICENSE)

## Contributing

[CONTRIBUTING.md](CONTRIBUTING.md) - terminal-only, real-behaviour-only,
honest-status-only.

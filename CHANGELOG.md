# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.3] - 2026-10-13

One-command setup and a troubleshooting-complete README.

### Changed
- `pip install -e .` now installs **everything**: the CLI dependencies plus
  the development tooling (`pytest`, `ruff`, `mypy`, `types-requests`). All
  are pure-Python wheels, so the Termux route needs no native toolchain.
  A single install is enough for `make test`, `make lint`, `make format`,
  and `make typecheck`. The `dev` extra is kept as a compatibility alias.
- README rewritten around the real first-run experience: the Installation
  section uses the one-command install, and the Troubleshooting section now
  includes every setup/CLI failure mode observed in practice with its exact
  fix (entry point not found, sourcing a console script, missing modules,
  stale shell hash, Python version gate) alongside the provider-side issues.
- `docs/troubleshooting.md` mirrors the new install/CLI section; the
  Makefile `install` target comment reflects the new behaviour.

## [0.1.2] - 2026-10-13

Presentation and resilience release.

### Changed
- Polished terminal output: rounded, dim-bordered tables with cyan headers,
  checkmark success lines, aligned `doctor` check marks, and human-friendly
  reward formatting (`1,000 USDC` instead of `1000.0 USDC`).
- Automatic base-URL failover: when a documented Gibwork host
  (`api.gib.work` / `api2.gib.work`) is unreachable (connection errors,
  timeouts, 5xx), the other documented host is probed once per session and
  adopted on success; the switch is reported by `gibwork status`, `gibwork
  test`, and `gibwork version`. Custom base URLs and 429/401/403 responses
  never trigger failover.
- Full quality gate verified on Python 3.11 **and** 3.12 (the CI matrix
  versions) locally.

### Fixed
- Rich-markup safety: untrusted text (bounty titles/descriptions, file
  paths, audit findings) is escaped before terminal rendering. Previously a
  bounty title or evidence path containing square brackets could crash the
  command (e.g. `submission check --project-path /abs/path` raised
  `MarkupError` because `[/abs]` parsed as a closing style tag) or silently
  swallow text (a table cell `Fix [bug]` rendered as `Fix`); the mandated
  estimate labels (`[estimate]`) were invisible in terminal output. Covered
  by `tests/unit/test_output_safety.py`.
- `doctor` now requires Python >= 3.11 (matching `requires-python`) instead
  of the stale 3.9 check.

## [0.1.1] - 2026-10-13

Hardening and live re-verification release.

### Changed
- Require Python 3.11+ (matches the project requirement); CI matrix now runs
  3.11 and 3.12.
- Declare `click` explicitly as a dependency (newer `typer` no longer pulls it
  in, but BountyPilot uses it directly).

### Fixed
- Official CLI bridge aligned with the real `@gibwork/cli` 0.2.4 contract:
  listing uses `task available`, detail uses `task get`; structured
  `CREDENTIAL_ERROR` payloads map to an honest "Authentication required"
  (exit 4) instead of a traceback; `gibwork status` reports
  "Authentication required" when the official CLI has no wallet; `gibwork
  test` probes a listing and explains the wallet requirement; bridge-mode
  search is documented and implemented client-side.
- Deep pagination without a session degrades gracefully: `bounty list --page N`
  (N > 1) returns an empty page with an explanatory note (table and JSON)
  instead of failing; the `show` fallback stops at the visible pages.
- `bounty list` / `bounty search` map provider errors to the documented exit
  codes (clean messages, no stack traces).
- `gibwork test` suggests `GIBWORK_BASE_URL` when the configured host is
  unreachable (e.g. datacenter IP blocked by a WAF).
- `scripts/install.sh` fails fast with an actionable message on Python < 3.11.

### Verified live (2026-10-13)
- `@gibwork/cli` 0.2.4 installed and driven through the bridge (status, auth
  status, capabilities, test, version, bounty list error path).
- Pagination probes: `page > 1` -> 401 `Sign in to view additional explore
  results`; `offset` ignored; `limit <= 15` unauthenticated ceiling confirmed.
- Full quality gate on Python 3.11: ruff, format, mypy (53 files), 93 tests
  (91 offline + 2 live).

## [0.1.0] - 2026-10-13

Initial release built for the Gibwork Developer Hackathon bounty.

### Added
- Terminal CLI `bountypilot` with the full command inventory: init, doctor,
  completion, config show/set, gibwork status/auth status/capabilities/test/version,
  bounty list/search/show/filter/recommend/compare, analyze (+ skills/difficulty/
  effort/requirements), plan, checklist, track add/list/show/status/remove/export/
  import, project plan/scaffold/inspect/test/audit/report, docs readme/setup/
  acceptance, evidence capture/list, report generate, submission check/package,
  reminders list/add/remove, watch <id>/watch list, interactive.
- Gibwork integration over the documented public API
  (`GET /explore`, `GET /tasks/{id}`) with bounded retries, throttling, and
  graceful handling of 401/403/429/5xx responses; optional official-CLI bridge.
- Local heuristic AI provider (no key required) and optional remote
  OpenAI-compatible provider with graceful degradation; every estimate labelled.
- SQLite storage with ordered migrations, transactions and unique constraints.
- Tracking lifecycle (Saved -> ... -> Abandoned) with validated transitions and
  safe import/export.
- Evidence capture with SHA-256 integrity hashes and secret redaction.
- Report generation (Markdown + JSON), docs generation, submission readiness
  checks and package archiving with a manifest.
- Reminders (persistent, timezone-aware; explicit about needing an OS scheduler
  for background execution) and periodic watch polling with change records.
- Security: secret redaction everywhere, restrictive file permissions, safe
  path handling, argument-array subprocess execution with timeouts.
- Test suite (offline by default; live Gibwork checks are opt-in).

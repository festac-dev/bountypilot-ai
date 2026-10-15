# Architecture

BountyPilot is a modular Python CLI. Commands never contain SQL or
provider-specific logic.

```
terminal
  |
  v
commands/          typer command layer; argument validation, output formatting
  |  (context.py builds one AppServices per invocation)
  v
services/          domain logic: bounty, analysis, tracking, evidence, docs,
  |                reporting, submission, reminder, watcher, project
  v
storage/                          integrations/
  database.py (migrations, tx)      gibwork/ (client, capabilities, health)
  repositories.py (all SQL)         ai/ (base, router, local, remote providers)
  |
  v
security/          redaction, path validation, safe subprocess execution
```

## Key rules

- **One integration interface.** `GibworkClient` is the only Gibwork seam;
  `PublicApiClient` (HTTP) and `OfficialCliBridge` (subprocess) implement it.
  The rest of the app cannot tell which is active.
- **One service container.** `AppServices` wires settings, database,
  repositories, the Gibwork client and the AI provider lazily. Read-only
  commands never create files.
- **Data provenance.** Models carry `origin` labels: `provider`,
  `local_cache`, `user`, `ai_estimate`, `verified_run`. Estimates are never
  presented as verified facts.
- **Exit codes.** 0 ok; 1 general; 2 usage; 3 configuration; 4
  integration/auth; 5 service unavailable; 6 validation; 7 security policy.
- **Offline-capable analysis.** The local heuristic provider needs no key, no
  network, no model. The remote provider is opt-in and degrades gracefully.
- **Storage.** SQLite with ordered migrations (`schema_migrations`), WAL,
  foreign keys ON, unique constraints, per-operation transactions.

## Module map

| Path | Responsibility |
|---|---|
| `src/bountypilot/main.py` | console entry point, exit-code plumbing |
| `src/bountypilot/cli.py` | command registration, global options, error mapping |
| `src/bountypilot/settings.py` | config precedence, validation, persistence |
| `src/bountypilot/output.py` | rich tables, strict JSON mode, exit codes |
| `src/bountypilot/core/` | validated dataclass models, input validation |
| `src/bountypilot/integrations/gibwork/` | public API client, CLI bridge, capabilities, health |
| `src/bountypilot/integrations/ai/` | provider abstraction + local heuristic + optional remote |
| `src/bountypilot/storage/` | SQLite database and repositories |
| `src/bountypilot/services/` | domain services used by commands |
| `src/bountypilot/security/` | redaction, path safety, subprocess policy |
| `src/bountypilot/commands/` | typer command modules |

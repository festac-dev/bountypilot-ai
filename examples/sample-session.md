# Sample BountyPilot session

Real terminal session recorded 2026-10-13 against the live Gibwork public API
(Python 3.11.10, Linux x86_64, BountyPilot 0.1.2). Output trimmed for
readability.

```text
$ bountypilot init
✔ BountyPilot initialized.
  Data directory: ~/.local/share/bountypilot
  Database: .../bountypilot.db (created)
  Config: created .../config.json

$ bountypilot doctor
  ✔ ok  python: Python 3.11.10
  ✔ ok  bountypilot: version 0.1.2
  ✔ ok  requests: requests 2.34.2
  ✔ ok  database: database readable
  ✔ ok  data_directory: writable
  ✔ ok  gibwork: reachable
✔ All checks passed.

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
│ d321ae8f │ Create an X     │ 400 CREDITS │ 2026-11-27 │ Social Media │ open  │
│          │ Thread About    │             │            │              │       │
[...]
Source: gibwork public listing - retrieved in 0.07s

$ bountypilot bounty show 1052f22d-3f87-4b1d-b0d7-71a60679e7fa
Gibwork Developer Hackathon Bounty
  ID: 1052f22d-3f87-4b1d-b0d7-71a60679e7fa
  URL: https://gib.work/bounty/1052f22d-3f87-4b1d-b0d7-71a60679e7fa
  Reward: 1,000 USDC
  Deadline: 2026-10-30T04:00:00.000Z
  Status: CREATED
  Open: True
  Poster: gibwork
  Tags: Development
  Source: local cache (retrieved 2026-10-13T08:15:08Z)

[...]

$ bountypilot analyze 1052f22d-3f87-4b1d-b0d7-71a60679e7fa
Complete analysis: Gibwork Developer Hackathon Bounty
  Bounty ID: 1052f22d-3f87-4b1d-b0d7-71a60679e7fa
  Provider: local-heuristic

Heuristic analysis of 'Gibwork Developer Hackathon Bounty': 7 requirement
sentence(s), 6 deliverable sentence(s), difficulty low (estimate), ~58.0h effort
(estimate).

Requirements (extracted):
  - The bounty must use Gibwork SDK, CLI, or MCP as a core part of the
implementation
  - The bounty must be a new use case, not a minor variation of an existing demo
  [...]

$ bountypilot track add 1052f22d-3f87-4b1d-b0d7-71a60679e7fa
✔ Tracking 1052f22d (status: saved).

$ bountypilot track status 1052f22d-3f87-4b1d-b0d7-71a60679e7fa evaluating
✔ Status of 1052f22d is now 'evaluating'.

$ bountypilot report generate 1052f22d-3f87-4b1d-b0d7-71a60679e7fa
✔ Report generated: ~/.local/share/bountypilot/exports/report-1052f22d.md
```

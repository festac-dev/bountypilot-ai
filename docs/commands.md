# Command Reference

All commands support the global options: `--help`, `--version`, `--verbose`,
`--quiet`, `--json`, `--no-color`, `--debug`, `--config <dir>`. Exit codes:
0 success, 1 general failure, 2 invalid usage, 3 configuration error,
4 integration/auth error, 5 service unavailable, 6 validation failure,
7 security policy violation.

## General
- `bountypilot --help` - command hierarchy with usage
- `bountypilot --version` - installed version
- `bountypilot init` - create config and data structures (idempotent)
- `bountypilot doctor` - environment, database, permissions and Gibwork checks
- `bountypilot completion bash|zsh|fish` - completion installation instructions

## Configuration
- `bountypilot config show` - effective configuration, secrets redacted
- `bountypilot config set <key> <value>` - validated, persisted setting

## Gibwork
- `bountypilot gibwork status` - Configured / Connected / Authentication required / Temporarily unavailable / Unsupported configuration
- `bountypilot gibwork auth status` - credential state without revealing secrets
- `bountypilot gibwork capabilities` - verified + explicitly unsupported operations
- `bountypilot gibwork test` - safe, read-only reachability check
- `bountypilot gibwork version` - client version if exposed

## Bounty discovery
- `bountypilot bounty list [--page N] [--limit N]` - public listing (cached locally)
- `bountypilot bounty search "<keywords>"` - server-side search
- `bountypilot bounty show <id> [--refresh]` - single bounty (cache first)
- `bountypilot bounty filter --min-reward N --max-reward N --tag T` - local filter on real fields
- `bountypilot bounty recommend --top N [--min-reward N]` - transparent scoring (reward/open/pool/deadline)
- `bountypilot bounty compare <id1> <id2>` - field-by-field diff

## Analysis and planning
- `bountypilot analyze <id>` - full analysis
- `bountypilot analyze skills|difficulty|effort|requirements <id>` - focused views
- `bountypilot plan <id>` - suggested implementation sequence (never executed)
- `bountypilot checklist <id>` - requirement/deliverable checklist

## Tracking
- `bountypilot track add <id> [--notes ...]`
- `bountypilot track list` / `track show <id>`
- `bountypilot track status <id> <status>` - validated lifecycle transitions
  (saved -> evaluating -> planned -> in progress -> blocked/completed/abandoned)
- `bountypilot track remove <id> [--yes]`
- `bountypilot track export [file]` / `track import <file> [--overwrite]`

## Project
- `bountypilot project plan <id>` - same service as `plan`
- `bountypilot project scaffold <path> <id> [--force]`
- `bountypilot project inspect <path>` - structure/config/tests (read-only)
- `bountypilot project test <path> [--command "..."]` - runs the configured suite, reports the real result
- `bountypilot project audit <path>` - static heuristic audit (not a security scan)
- `bountypilot project report <id>` - same service as `report generate`

## Documentation
- `bountypilot docs readme <id>` - README draft starting with the Use Case / Value / Toolset block
- `bountypilot docs setup <id>` - setup guide draft (sample output labelled illustrative)
- `bountypilot docs acceptance <id>` - acceptance criteria draft

## Evidence
- `bountypilot evidence capture <description> [--kind K] [--file F] [--bounty ID]`
  - kinds: transcript, command_output, test_summary, log, screenshot, report
  - text is read from stdin (paste, Ctrl-D to finish); secrets are redacted; SHA-256 recorded
- `bountypilot evidence list`

## Reporting
- `bountypilot report generate <id>` - Markdown + JSON report from stored data

## Submission
- `bountypilot submission check <id> [--repo-url ...] [--demo-video-url ...]
  [--project-path ...] [--discord-sessions-attended] [--hackathon-role-awarded]
  [--form-submitted]` - evidence-based readiness; attestations stay unverified
- `bountypilot submission package <id> [--out DIR]` - organized directory + zip with manifest (never auto-submits)

## Reminders
- `bountypilot reminders list` - plus the note that background execution needs an OS scheduler
- `bountypilot reminders add <id> [--lead-hours N]` - timezone-aware when a deadline exists
- `bountypilot reminders remove <row-number>`

## Monitoring
- `bountypilot watch <id> [--interval S] [--iterations N]` - periodic polling with change records
- `bountypilot watch list` - watched bounties
- `bountypilot watch <id> --remove` - stop watching

## Interactive
- `bountypilot interactive` - repl commands dispatched through the same commands; exit/quit/Ctrl-D leaves

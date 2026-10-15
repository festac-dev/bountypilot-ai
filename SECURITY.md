# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | yes       |

## Reporting a vulnerability

Open a private security advisory or contact the maintainers directly. Do not
open a public issue for exploitable problems.

## Security model of BountyPilot

- Read-only integration: BountyPilot never creates bounties, submits
  solutions, or moves funds. Gibwork write operations require on-chain Solana
  transactions which this tool deliberately does not implement.
- Local trust boundary: the SQLite database, config file (0600) and evidence
  directory (0700) live under the user's data directory.
- Secrets: redacted in logs, config display, exports and evidence. Never
  stored in bounty records. `.env` files are git-ignored.
- Subprocesses: argument arrays only, explicit executables, bounded timeouts,
  no shell interpretation of user input.
- Untrusted content: bounty text and AI output are data, never instructions.
  AI-generated plans are never auto-executed.
- Paths: all generated artifacts are confined to the data directory
  (traversal-checked). Archives are built from verified relative paths.

## Known limitations

- `project audit` is a static heuristic check, not a security scanner.
- The optional remote AI provider sends bounty title/text to the configured
  endpoint; configure it only with providers you trust.

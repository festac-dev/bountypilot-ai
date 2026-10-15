# Security

## Controls implemented and tested

- **Secret redaction** (`security/redaction.py`): config keys and secret-looking
  values are redacted in `config show`, logs, evidence, exports and reports.
  Tests: `tests/unit/test_redaction.py`, `tests/security/test_security.py`.
- **Restrictive file permissions**: data directory 0700, config file 0600
  (atomic writes), secure temp files. Test: `test_write_private_file_mode`.
- **Path traversal protection** (`core/validation.py`): generated artifacts are
  confined to the data directory; archive entries and evidence paths are
  checked. Tests: `test_safe_output_path_blocks_traversal`.
- **Safe subprocess execution** (`security/command_execution.py`): argument
  arrays only, explicit executable paths, bounded timeouts, 2 MB output cap,
  never `shell=True` with user input. Tests: `test_run_command_*`.
- **Bounded retries and throttling** for Gibwork GETs; writes are never
  auto-repeated (none exist).
- **Untrusted content**: bounty text and AI output are treated as data.
  Embedded instructions cannot change security policy; AI-generated plans are
  never auto-executed (`plan`/`checklist` only print).
- **SQL integrity**: parameterized queries only, transactions, unique
  constraints, foreign keys ON. All SQL lives in repositories.
- **No credential storage** in bounty records, evidence or exports.

## Operations that need user confirmation

- `track remove` (unless `--yes`)
- `project scaffold` into a non-empty directory (`--force` required)

## Dependency checks

- CI runs `pip-audit` (best effort).
- `make audit` locally.
- Runtime dependencies are limited to `typer`, `rich`, `requests`.

## Not a security scanner

`project audit` performs static heuristic checks (missing README/tests/LICENSE,
obvious `eval()`/`shell=True` usage, `.env` presence). It does not replace
tests, dependency audits or a real security review.

## Reporting

See SECURITY.md for the disclosure policy.

# Configuration

## Precedence (highest first)

1. Command-line overrides (`--config <dir>` sets the data directory; `--json`
   forces JSON output)
2. Environment variables (and a `.env` file in the working directory)
3. User config file (`<data directory>/config.json`)
4. Safe defaults

## Reference

| Key | Default | Explanation |
|---|---|---|
| `GIBWORK_INTEGRATION_MODE` | `public_api` | `public_api` or `official_cli` |
| `GIBWORK_BASE_URL` | `https://api.gib.work` | public API base URL |
| `GIBWORK_CLI_PATH` | (empty) | official CLI executable for `official_cli` mode |
| `GIBWORK_TIMEOUT_SECONDS` | `20` | per-request timeout (1-120) |
| `GIBWORK_RETRY_LIMIT` | `2` | bounded retries for idempotent GETs (0-5) |
| `GIBWORK_REQUEST_INTERVAL_SECONDS` | `1.0` | minimum interval between requests |
| `GIBWORK_API_KEY` | (empty) | secret; redacted everywhere; see docs/gibwork-integration.md |
| `AI_PROVIDER` | `local` | `local` (heuristic, offline) or `remote` (OpenAI-compatible) |
| `LOCAL_MODEL_NAME` | `bountypilot-heuristic-v1` | informational label |
| `AI_BASE_URL` | (empty) | remote provider base URL |
| `AI_API_KEY` | (empty) | secret; never sent to Gibwork |
| `AI_MODEL` | (empty) | remote model name |
| `DATABASE_URL` | (empty) | explicit sqlite path (e.g. `sqlite:////path/x.db`); default `<data>/bountypilot.db` |
| `DATA_DIRECTORY` | `~/.local/share/bountypilot` (XDG-aware) | where config/db/evidence/exports live |
| `LOG_LEVEL` | `WARNING` | `DEBUG`/`INFO`/`WARNING`/`ERROR`; secrets redacted in logs |
| `OUTPUT_FORMAT` | `table` | default output; global `--json` overrides |
| `REQUEST_TIMEOUT_SECONDS` | `20` | generic timeout |
| `MAX_RETRIES` | `2` | generic retry bound |

`.env.example` documents the same variables in plain language — what each one
does, its allowed values and default, when you actually need to change it, and
ready-made scenarios (remote AI, official CLI, slow connections, custom data
directory). Copy it to `.env` and keep only the lines you want to change; an
empty value always means "use the default". Never commit a filled `.env`.

## Commands

```bash
bountypilot config show                 # effective values, secrets redacted
bountypilot config set LOG_LEVEL DEBUG  # validate + persist to config.json
bountypilot config set BAD_KEY x        # exit code 3 with supported keys listed
```

## Secret handling

- `GIBWORK_API_KEY` and `AI_API_KEY` are redacted in `config show`, logs,
  exports, evidence and reports.
- The config file is written atomically with mode 0600.
- Secrets are never stored in bounty records, evidence, or exported reports.

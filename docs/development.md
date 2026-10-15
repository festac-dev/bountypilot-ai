# Development

## Layout

See docs/architecture.md. In short: commands -> services -> repositories /
integrations. No SQL in commands; no provider details outside the
`integrations/` package.

## Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"   # CLI + dev tooling (Termux: see README)
```

## Everyday commands

```bash
make test          # offline test suite
make lint          # ruff check
make format        # ruff format --check
make typecheck     # mypy (best effort)
make test-live     # opt-in live Gibwork checks (network)
make dev-check     # everything, via scripts/dev-check.sh
```

## Testing approach

- `tests/conftest.py` provides an isolated data directory (`--config`) and a
  `FakeGibworkClient` implementing the same interface as the real adapter.
- The offline suite never touches the network and needs no credentials.
- `tests/integration/test_live_gibwork.py` is the only network test and runs
  only with `BOUNTYPILOT_LIVE_TESTS=1`.
- Contract tests pin the HTTP adapter's error handling with a mocked
  `requests` transport.

## Adding a command

1. Add the service method (or a new service) - real logic, no stubs.
2. Register the command in `cli.py` (sub-app or top-level) with complete help
   text and validated arguments.
3. Support JSON output via the shared `output` helpers.
4. Map errors to the documented exit codes via `handle_error`.
5. Add tests: unit for logic, integration for the CLI surface.

## Code style

- Ruff (`E,F,W,I,UP,B,S`) with line length 100.
- Type hints everywhere practical; `from __future__ import annotations`.
- No comments unless they explain a non-obvious decision.

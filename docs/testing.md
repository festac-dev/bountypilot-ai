# Testing

## Test layout

```
tests/
  conftest.py            isolated data dir + FakeGibworkClient fixtures
  unit/                  settings, redaction, models, analysis, repositories, AI providers
  contract/              HTTP adapter behaviour with a mocked transport
  integration/           full CLI flows (fake client); test_live_gibwork.py = opt-in live
  security/              redaction, permissions, path safety, subprocess policy
  end_to_end/            complete workflows: evidence, docs, packaging, watch, reminders
  fixtures/              (fixture data lives in conftest.py, captured public data)
```

## Commands

```bash
make test        # pytest tests -q  (offline, hermetic, no credentials)
make test-live   # BOUNTYPILOT_LIVE_TESTS=1 pytest tests/integration/test_live_gibwork.py
make lint        # ruff check src tests
make format      # ruff format --check src tests
make typecheck   # mypy src/bountypilot (best effort)
```

## What the suite covers

- Configuration precedence, validation failures, secret redaction.
- Database creation, migrations, corruption handling, idempotent upserts,
  import/export conflict handling.
- Bounty model validation against malformed provider data.
- Gibwork adapter: 401/403/404/429/5xx handling, invalid JSON, network errors,
  rejected-credential retry, detail-endpoint fallback.
- Full CLI workflows with the fake client (no network).
- Security: log redaction, file modes, traversal protection, subprocess policy.
- AI: local extraction quality, focus variants, remote provider parsing and
  graceful degradation.
- Opt-in live checks against the real public API.

## Results

See docs/IMPLEMENTATION_STATUS.md for the latest recorded run.

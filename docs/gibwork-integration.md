# Gibwork Integration

Status: **Implemented and tested** (offline tests) / **live-verified** against
the real public API during development.

## Which Gibwork toolset is used

BountyPilot integrates with Gibwork through the **official public REST API** -
the documented read surface that Gibwork itself publishes and that the official
`@gibwork/sdk` (TypeScript) and the official example app use:

- `GET {base}/explore?page=1&limit=15&search=<keywords>&tags=<t1,t2>` - public
  bounty listing with server-side search and pagination parameters.
- `GET {base}/tasks/{id}` - single bounty detail (documented; may require an
  authenticated session on some networks).

Endpoints are documented in Gibwork's own repository
`gibwork/gibwork-api-examples` (Next.js example app) which names:

- `GET https://api2.gib.work/explore`
- `GET https://api2.gib.work/tasks/{id}`
- `POST https://api2.gib.work/tasks/public/transaction` (task creation, requires wallet signing - **not used by BountyPilot**)

BountyPilot defaults `GIBWORK_BASE_URL` to `https://api.gib.work` (the public
read surface), which served live data during development. `api2.gib.work`
rejected requests from datacenter IPs with HTTP 403 during testing; users on
residential networks can switch the base URL if they prefer.

### Automatic base-URL failover

When the configured base URL is one of the two documented Gibwork hosts and
requests fail with connection errors, timeouts, or 5xx responses, BountyPilot
probes the other documented host once per session and, if it answers, uses it
for the rest of the session. The switch is reported honestly by
`gibwork status` (Failover line), `gibwork test`, and `gibwork version`
(which shows the active base). Behaviour:

- only applies to `https://api.gib.work` and `https://api2.gib.work`; a custom
  base URL (e.g. a proxy) is never overridden;
- never triggers on rate limiting (429) or authentication responses
  (401/403), so provider auth gates and WAF blocks are reported as such
  instead of silently shifting hosts;
- if the alternative host also fails, the original error is raised with a
  note that both hosts were tried.

## Why not the npm SDK/CLI directly

`@gibwork/sdk`, `@gibwork/cli` and `@gibwork/mcp` are Node.js (>= 22) packages.
BountyPilot is a Python CLI that must run on Termux and Linux with minimal
native dependencies. Therefore:

1. **Primary (Implemented and tested):** a Python adapter over the same
   documented public API - no Node.js required.
2. **Optional (Partially supported / awaiting configuration):** an
   `official_cli` mode delegates listing/detail to the official CLI via a
   subprocess bridge when `GIBWORK_INTEGRATION_MODE=official_cli` and
   `GIBWORK_CLI_PATH` point at an installed `@gibwork/cli`. This mode is
   implemented and covered by tests with a stub; live delegation requires the
   official package installed locally.

## Official CLI bridge (verified against @gibwork/cli 0.2.4)

The bridge was re-verified live against the real `@gibwork/cli` (installed via
`npm install -g @gibwork/cli`, Node.js 24, 2026-10-13):

- Listing maps to `gibwork task available --page N --limit N` (the CLI's
  documented discovery command; limits 1-100).
- Detail maps to `gibwork task get <task-id>`.
- The official CLI requires a configured wallet for **every** task operation,
  including public discovery: without one it exits 10 with
  `{"ok":false,"error":{"code":"CREDENTIAL_ERROR",...}}` on stderr. The bridge
  maps this to "Authentication required" (exit code 4) with the CLI's message.
- The official CLI exposes no server-side search; bridge-mode keyword/tag
  filtering is applied client-side over the fetched page (documented in
  `gibwork capabilities`).
- Live listing through the bridge therefore requires a Solana keypair
  configured for the official CLI (`keypair-path` in a profile, `--keypair`
  file, or `--private-key-stdin`). Without it, BountyPilot reports the gap
  honestly instead of faking data.

## Verified capabilities

| Operation | Status | Notes |
|---|---|---|
| List bounties | Implemented and tested | `GET /explore`; live check returned 8 bounties on 2026-10-13 |
| Server-side search | Implemented | `search` parameter honoured by the API |
| Pagination parameters | Partially supported | page 1 works unauthenticated (limit <= 15); deeper pages returned HTTP 401 without a session. BountyPilot degrades gracefully: page > 1 returns an empty page with an explanatory note instead of failing |
| Single bounty detail | Implemented | documented `/tasks/{id}`; falls back to locating the bounty in the listing |
| Health check | Implemented and tested | `gibwork test` is read-only |
| Bounty creation | Unsupported by the provider (for CLI tools) | requires a signed Solana wallet transaction; deliberately not implemented |
| Submission upload | Unsupported by the provider (for CLI tools) | requires an authenticated Gibwork session |
| Wallet authentication | Not implemented | no documented unauthenticated auth flow; `GIBWORK_API_KEY` is sent if configured but the public API rejected it during testing (BountyPilot reports this honestly) |

## Error handling

- Timeouts and connection errors -> `GibworkUnavailable` (exit code 5)
- 401/403 -> authentication handling; a configured-but-rejected key triggers
  one unauthenticated retry and is reported by `gibwork auth status`
- 429 -> `GibworkRateLimited` (bounded backoff between retries)
- 5xx -> `GibworkUnavailable` with bounded retries
- invalid JSON -> `GibworkInvalidResponse`
- unknown id -> `GibworkNotFound`

Retries are bounded (`GIBWORK_RETRY_LIMIT`, default 2) and only ever applied
to idempotent GETs. Requests are throttled with a minimum interval
(`GIBWORK_REQUEST_INTERVAL_SECONDS`, default 1s).

## Data provenance

Every stored bounty carries `origin` ("provider") and `retrieved_at`.
Analysis payloads carry `origin: "ai_estimate"`. Local tracking status is
independent from the provider status. Nothing fetched from Gibwork is
presented as verified beyond the moment of retrieval.

## Observed pagination behaviour (re-verified 2026-10-13)

Probed against the live API without a session:

- `GET /explore?page=1&limit=15` -> 200 (15 is the unauthenticated ceiling;
  `limit=16` returns 401 with body `Sign in to view additional explore results`).
- `GET /explore?page=2` -> 401 (any page > 1 requires an authenticated session).
- `GET /explore?offset=N` -> 200 but the `offset` parameter is ignored
  server-side (same results as page 1), so it cannot substitute for pagination.

Consequence: without a session the visible window is page 1 with up to 15
bounties. BountyPilot handles this honestly: requesting a deeper page returns
an empty result set plus a note (surfaced in both table and JSON output) that
explains the ceiling and states the total listing size when the listing fits
on page 1. The `get_task` listing fallback also stops at the visible pages
instead of surfacing an authentication error.

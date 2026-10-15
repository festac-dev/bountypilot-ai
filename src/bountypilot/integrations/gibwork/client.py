"""Gibwork integration adapter.

Integration method (documented in docs/gibwork-integration.md):
- Primary: Gibwork's official public read API (`GET {base}/explore`, `GET {base}/tasks/{id}`),
  the same documented endpoints used by gibwork's own example app and official SDK.
- Optional: delegation to the official `@gibwork/cli` when GIBWORK_CLI_PATH is configured
  (mode = official_cli; partially supported, requires Node.js and the official package).

The rest of BountyPilot only sees `GibworkClient`; provider details stay here.
Retries are bounded and applied to idempotent GETs only.
"""

from __future__ import annotations

import threading
import time
from typing import Any, NoReturn, Optional, Sequence

import requests

from bountypilot.core.models import Bounty, utc_now_iso
from bountypilot.integrations.gibwork.exceptions import (
    GibworkAuthenticationRequired,
    GibworkError,
    GibworkInvalidResponse,
    GibworkNotFound,
    GibworkRateLimited,
    GibworkUnavailable,
)
from bountypilot.logging_config import get_logger
from bountypilot.security.command_execution import run_command

log = get_logger("bountypilot.gibwork")

USER_AGENT = "bountypilot-ai/0.1.3 (terminal CLI; Gibwork public API client)"
MAX_PAGE_LIMIT = 15  # observed server maximum for the public explore endpoint
# Both hosts are documented in docs/gibwork-integration.md (gibwork's own example
# app names api2.gib.work; api.gib.work serves the public listing). If the
# configured host is unreachable, the other one is probed once and adopted.
KNOWN_BASE_URLS = ("https://api.gib.work", "https://api2.gib.work")


class ExplorePage:
    def __init__(
        self,
        results: Sequence[Bounty],
        page: int,
        limit: int,
        total: int,
        last_page: int,
        note: Optional[str] = None,
    ):
        self.results = list(results)
        self.page = page
        self.limit = limit
        self.total = total
        self.last_page = last_page
        self.note = note

    def to_dict(self) -> dict[str, Any]:
        return {
            "page": self.page,
            "limit": self.limit,
            "total": self.total,
            "last_page": self.last_page,
            "note": self.note,
            "retrieved_at": utc_now_iso(),
            "results": [b.to_dict() for b in self.results],
        }


class GibworkClient:
    """Interface every adapter implements. Read-only by design."""

    mode = "abstract"

    def explore(
        self,
        page: int = 1,
        limit: int = MAX_PAGE_LIMIT,
        search: str = "",
        tags: Optional[Sequence[str]] = None,
    ) -> ExplorePage:
        raise NotImplementedError

    def get_task(self, bounty_id: str) -> Bounty:
        raise NotImplementedError

    def health(self) -> dict[str, Any]:
        raise NotImplementedError

    def version(self) -> Optional[str]:
        return None

    def capabilities(self) -> dict[str, Any]:
        raise NotImplementedError


class PublicApiClient(GibworkClient):
    """HTTP client over the documented Gibwork public read API."""

    mode = "public_api"

    def __init__(
        self,
        base_url: str = "https://api.gib.work",
        timeout_seconds: float = 20.0,
        max_retries: int = 2,
        request_interval_seconds: float = 1.0,
        api_key: str = "",
        verify_tls: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout_seconds
        self.max_retries = max(0, int(max_retries))
        self.request_interval = max(0.0, float(request_interval_seconds))
        self.api_key = api_key
        self.verify_tls = verify_tls
        self._lock = threading.Lock()
        self._last_request_at = 0.0
        self._last_health: Optional[dict[str, Any]] = None
        self.auth_rejected = False
        # Failover state: when the configured host is unreachable, the other
        # documented host is probed once and adopted for the session.
        self.failover_note: Optional[str] = None
        self._failover_attempted = False

    # -- plumbing -----------------------------------------------------------

    def _throttle(self) -> None:
        with self._lock:
            wait = self.request_interval - (time.monotonic() - self._last_request_at)
            if wait > 0:
                time.sleep(wait)
            self._last_request_at = time.monotonic()

    def _headers(self, with_auth: bool = True) -> dict[str, str]:
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        if with_auth and self.api_key:
            # Only sent when the user explicitly configured a key; never logged.
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _get_json(self, path: str, params: Optional[dict[str, Any]] = None) -> Any:
        try:
            return self._request(path, params=params, with_auth=not self.auth_rejected)
        except GibworkRateLimited:
            # Rate limiting is not unreachability; never shift hosts on a 429.
            raise
        except GibworkUnavailable as exc:
            return self._request_with_failover(path, params, exc)

    def _request_with_failover(
        self,
        path: str,
        params: Optional[dict[str, Any]],
        primary_error: GibworkUnavailable,
    ) -> Any:
        """Retry once against the other documented host when the configured one is unreachable.

        Only applies to known Gibwork hosts (never to a custom base URL, which may be
        a deliberate proxy choice) and only once per client session.
        """
        alternate = self._alternate_base_url()
        if alternate is None or self._failover_attempted:
            raise primary_error
        self._failover_attempted = True
        primary = self.base_url
        try:
            data = self._request(path, params=params, with_auth=not self.auth_rejected, base_url=alternate)
        except GibworkError:
            # Both hosts failed; surface the primary failure with an honest hint.
            raise GibworkUnavailable(
                f"{primary_error.message} The alternative host {alternate} was also unreachable "
                "or rejected the request."
            ) from None
        self.base_url = alternate
        self.failover_note = f"Primary base {primary} was unreachable; requests now use {alternate} for this session."
        log.debug("failover from %s to %s", primary, alternate)
        return data

    def _alternate_base_url(self) -> Optional[str]:
        """The other documented Gibwork host, or None for custom base URLs."""
        normalized = self.base_url.rstrip("/")
        if normalized not in KNOWN_BASE_URLS:
            return None
        return KNOWN_BASE_URLS[1 - KNOWN_BASE_URLS.index(normalized)]

    def _request(
        self,
        path: str,
        params: Optional[dict[str, Any]] = None,
        with_auth: bool = True,
        base_url: Optional[str] = None,
    ) -> Any:
        base = (base_url or self.base_url).rstrip("/")
        url = f"{base}{path}"
        last_error: GibworkError | None = None
        for attempt in range(self.max_retries + 1):
            self._throttle()
            try:
                log.debug("GET %s (attempt %d)", path, attempt + 1)
                response = requests.get(
                    url,
                    params=params or {},
                    headers=self._headers(with_auth=with_auth),
                    timeout=self.timeout,
                    verify=self.verify_tls,
                )
            except requests.Timeout:
                last_error = GibworkUnavailable(f"Gibwork request timed out: {url}")
                log.debug("timeout on %s", path)
                continue
            except requests.RequestException as exc:
                last_error = GibworkUnavailable(f"Cannot reach Gibwork at {base}.")
                log.debug("network error on %s: %s", path, type(exc).__name__)
                continue

            if response.status_code == 200:
                try:
                    return response.json()
                except ValueError as exc:
                    raise GibworkInvalidResponse(f"Gibwork returned non-JSON data for {path}.") from exc
            if response.status_code == 404:
                raise GibworkNotFound(f"No resource at {path}.")
            if response.status_code in (401, 403):
                if with_auth and self.api_key:
                    # A configured credential was rejected. Degrade gracefully:
                    # retry unauthenticated and remember the rejection honestly.
                    log.debug(
                        "configured credential rejected (HTTP %d); retrying unauthenticated",
                        response.status_code,
                    )
                    self.auth_rejected = True
                    return self._request(path, params=params, with_auth=False)
                raise GibworkAuthenticationRequired(
                    f"Gibwork rejected the request (HTTP {response.status_code}). "
                    "Unauthenticated access covers page 1 of the public listing; "
                    "deeper pagination or this endpoint requires an authenticated session."
                )
            if response.status_code == 429:
                last_error = GibworkRateLimited()
                log.debug("rate limited on %s", path)
                time.sleep(min(2**attempt, 8))
                continue
            if 500 <= response.status_code < 600:
                last_error = GibworkUnavailable(f"Gibwork server error (HTTP {response.status_code}).")
                continue
            raise GibworkError(f"Gibwork returned HTTP {response.status_code} for {path}.")
        raise last_error or GibworkUnavailable("Gibwork request failed.")

    # -- public interface ----------------------------------------------------

    def explore(
        self,
        page: int = 1,
        limit: int = MAX_PAGE_LIMIT,
        search: str = "",
        tags: Optional[Sequence[str]] = None,
    ) -> ExplorePage:
        if page < 1:
            page = 1
        limit = max(1, min(int(limit), MAX_PAGE_LIMIT))
        params: dict[str, Any] = {"page": page, "limit": limit}
        if search:
            params["search"] = search
        if tags:
            params["tags"] = ",".join(t for t in tags if t)
        try:
            data = self._get_json("/explore", params=params)
        except GibworkAuthenticationRequired:
            if page <= 1:
                raise
            # Observed provider behaviour: unauthenticated access covers page 1
            # only (limit <= 15); deeper pages return HTTP 401. Degrade honestly
            # instead of failing the whole listing.
            note = (
                f"Gibwork allows unauthenticated access to page 1 only (limit <= {MAX_PAGE_LIMIT}); "
                f"page {page} requires an authenticated session."
            )
            total = self._listing_total_unauthenticated()
            if total is not None and total <= limit:
                note += (
                    f" The public listing currently contains {total} bounties, so page 1 already includes all of them."
                )
            return ExplorePage(results=[], page=page, limit=limit, total=total or 0, last_page=page, note=note)
        if not isinstance(data, dict) or "results" not in data:
            raise GibworkInvalidResponse("Gibwork explore response is missing 'results'.")
        bounties = [Bounty.from_api(r, base_url="https://gib.work") for r in data["results"]]
        return ExplorePage(
            results=bounties,
            page=int(data.get("page", page)),
            limit=int(data.get("limit", limit)),
            total=int(data.get("total", len(bounties))),
            last_page=int(data.get("lastPage", 1)),
        )

    def _listing_total_unauthenticated(self) -> Optional[int]:
        """Best-effort total size of the public listing via a page-1 probe."""
        try:
            data = self._get_json("/explore", params={"page": 1, "limit": 1})
            if isinstance(data, dict):
                return int(data.get("total", 0))
        except GibworkError:
            log.debug("could not determine listing total during pagination degradation")
        return None

    def get_task(self, bounty_id: str) -> Bounty:
        """Retrieve one bounty.

        The detail endpoint is only reachable with an authenticated session on
        some networks; when it fails, fall back to locating the bounty in the
        public explore listing (documented limitation).
        """
        try:
            data = self._get_json(f"/tasks/{bounty_id}")
            if isinstance(data, dict):
                if "id" not in data and "task" in data and isinstance(data["task"], dict):
                    data = data["task"]
                return Bounty.from_api(data, base_url="https://gib.work")
        except (GibworkNotFound, GibworkAuthenticationRequired, GibworkUnavailable):
            log.debug("detail endpoint unavailable for %s; falling back to explore", bounty_id)

        page = 1
        while True:
            try:
                page_data = self.explore(page=page, limit=MAX_PAGE_LIMIT)
            except GibworkAuthenticationRequired:
                # Deep pagination is authenticated-only; stop at what is visible.
                log.debug("pagination stopped at page %d (authentication required)", page)
                break
            for bounty in page_data.results:
                if bounty.id == bounty_id.lower():
                    return bounty
            if page >= page_data.last_page or page >= 10:
                break
            page += 1
        raise GibworkNotFound(f"Bounty {bounty_id} was not found in the public listing.")

    def health(self) -> dict[str, Any]:
        try:
            data = self._get_json("/explore", params={"page": 1, "limit": 1})
            self._last_health = {
                "reachable": True,
                "checked_at": utc_now_iso(),
                "listing_total": int(data.get("total", 0)) if isinstance(data, dict) else None,
                "auth_state": "rejected"
                if self.auth_rejected
                else ("configured" if self.api_key else "unauthenticated"),
                "base_url": self.base_url,
                "failover_note": self.failover_note,
            }
        except GibworkError as exc:
            self._last_health = {
                "reachable": False,
                "checked_at": utc_now_iso(),
                "error": str(exc.message),
                "auth_state": "rejected"
                if self.auth_rejected
                else ("configured" if self.api_key else "unauthenticated"),
                "base_url": self.base_url,
                "failover_note": self.failover_note,
            }
        return self._last_health

    def version(self) -> Optional[str]:
        return f"public-api ({self.base_url})"

    def capabilities(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "base_url": self.base_url,
            "supported": {
                "list_bounties": True,
                "search_bounties": True,
                "get_bounty": "documented detail endpoint; falls back to the public listing",
                "health_check": True,
            },
            "unsupported": {
                "create_bounty": "requires an authenticated Solana wallet transaction",
                "submit_solution": "requires an authenticated Gibwork session",
                "user_authentication": "no documented unauthenticated auth flow; API key accepted when provided",
                "pagination_beyond_page_1": "may return HTTP 401 without an authenticated session",
            },
        }


class OfficialCliBridge(GibworkClient):
    """Delegate listing/detail to the official `@gibwork/cli` (Node.js).

    Partially supported: requires Node.js and `npm install -g @gibwork/cli`
    (verified against @gibwork/cli 0.2.4). The official CLI requires a configured
    wallet for every task operation, including public discovery
    (`CREDENTIAL_ERROR` otherwise). It exposes no server-side search, so
    keyword/tag filtering here is applied client-side over the fetched page.
    """

    mode = "official_cli"

    def __init__(self, cli_path: str, timeout_seconds: float = 30.0) -> None:
        if not cli_path:
            raise ValueError("OfficialCliBridge requires a CLI path.")
        self.cli_path = cli_path
        self.timeout = timeout_seconds

    def _invoke(self, args: Sequence[str]) -> Any:
        result = run_command(
            [self.cli_path, *args, "--json"],
            timeout_seconds=int(self.timeout),
        )
        if result.timed_out:
            raise GibworkUnavailable("Official Gibwork CLI timed out.")
        if result.exit_code not in (0, None):
            # Official CLI 0.2.4 reports errors as JSON on stderr with exit code 10.
            self._raise_provider_error(result.stderr or result.stdout or "official CLI failed")
        try:
            import json

            return json.loads(result.stdout)
        except ValueError as exc:
            raise GibworkInvalidResponse("Official CLI output was not valid JSON.") from exc

    @staticmethod
    def _raise_provider_error(raw: str) -> NoReturn:
        import json

        message = raw.strip()[:500]
        code = ""
        try:
            payload = json.loads(message)
            if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
                code = str(payload["error"].get("code", ""))
                message = str(payload["error"].get("message", message))
        except ValueError:
            pass
        if code == "CREDENTIAL_ERROR" or "auth" in message.lower() or "401" in message or "403" in message:
            raise GibworkAuthenticationRequired(f"The official Gibwork CLI requires a configured wallet: {message}")
        if code in ("NETWORK_ERROR", "TIMEOUT", "SERVER_ERROR"):
            raise GibworkUnavailable(f"Official Gibwork CLI could not reach Gibwork: {message}")
        raise GibworkError(f"Official Gibwork CLI failed ({code or 'unknown error'}): {message}")

    @staticmethod
    def _unwrap(payload: Any, list_keys: Sequence[str], item_keys: Sequence[str]) -> Any:
        """Normalise the CLI's JSON envelope ({ok: true, ...}) into raw data."""
        if isinstance(payload, dict):
            if payload.get("ok") is False:
                error = payload.get("error")
                message = (
                    str(error.get("message", "official CLI failed"))
                    if isinstance(error, dict)
                    else "official CLI failed"
                )
                OfficialCliBridge._raise_provider_error(message)
            for key in list_keys:
                if key in payload and isinstance(payload[key], list):
                    return payload[key]
            for key in item_keys:
                if key in payload and isinstance(payload[key], dict):
                    return payload[key]
            return payload
        return payload

    @staticmethod
    def _filter_client_side(bounties: list[Bounty], search: str, tags: Optional[Sequence[str]]) -> list[Bounty]:
        """The official CLI has no server-side search; filter the fetched page."""
        needle = search.strip().lower()

        def matches(bounty: Bounty) -> bool:
            if needle:
                haystack = " ".join(filter(None, [bounty.title, bounty.content, " ".join(bounty.tags)])).lower()
                if needle not in haystack:
                    return False
            for tag in tags or []:
                if tag and tag.lower() not in [t.lower() for t in bounty.tags]:
                    return False
            return True

        return [b for b in bounties if matches(b)]

    def explore(
        self,
        page: int = 1,
        limit: int = MAX_PAGE_LIMIT,
        search: str = "",
        tags: Optional[Sequence[str]] = None,
    ) -> ExplorePage:
        if page < 1:
            page = 1
        args = ["task", "available", "--page", str(page), "--limit", str(max(1, min(int(limit), 100)))]
        data = self._invoke(args)
        results = self._unwrap(data, list_keys=("tasks", "results"), item_keys=())
        if not isinstance(results, list):
            raise GibworkInvalidResponse("Official CLI listing output was unexpected.")
        bounties = [Bounty.from_api(r) for r in results]
        bounties = self._filter_client_side(bounties, search, tags)
        return ExplorePage(bounties, page=page, limit=limit, total=len(bounties), last_page=page)

    def get_task(self, bounty_id: str) -> Bounty:
        data = self._invoke(["task", "get", bounty_id])
        payload = self._unwrap(data, list_keys=(), item_keys=("task",))
        return Bounty.from_api(payload)

    def health(self) -> dict[str, Any]:
        result = run_command([self.cli_path, "--version"], timeout_seconds=10)
        health: dict[str, Any] = {
            "reachable": result.ok,
            "checked_at": utc_now_iso(),
            "error": None if result.ok else (result.stderr or "CLI not executable"),
            "cli_version": result.stdout.strip() if result.ok else None,
        }
        if result.ok:
            try:
                page = self.explore(limit=1)
                health["listing_total"] = page.total
                health["authenticated"] = True
            except GibworkAuthenticationRequired:
                health["authenticated"] = False
                health["note"] = (
                    "The official Gibwork CLI requires a configured wallet for task operations; "
                    "configure the CLI (keypair or profile) to enable live listing."
                )
            except GibworkError as exc:
                health["note"] = f"Listing probe failed: {exc.message}"
        return health

    def version(self) -> Optional[str]:
        result = run_command([self.cli_path, "--version"], timeout_seconds=10)
        return result.stdout.strip() if result.ok else None

    def capabilities(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "cli_path": self.cli_path,
            "supported": {
                "list_bounties": True,
                "search_bounties": "client-side only over the fetched page (official CLI has no server-side search)",
                "get_bounty": True,
                "health_check": True,
            },
            "unsupported": {
                "create_bounty": "not exposed by this read-only bridge",
                "submit_solution": "not exposed by this read-only bridge",
                "server_side_search": "the official CLI offers no search parameter on task discovery",
                "unauthenticated_listing": "the official CLI requires a configured wallet for every task operation",
            },
        }


def create_client(settings) -> GibworkClient:
    """Factory used by commands; picks the adapter from configuration."""
    if settings.gibwork_integration_mode == "official_cli":
        if not settings.gibwork_cli_path:
            from bountypilot.exceptions import GibworkNotConfigured

            raise GibworkNotConfigured("GIBWORK_INTEGRATION_MODE is 'official_cli' but GIBWORK_CLI_PATH is not set.")
        return OfficialCliBridge(settings.gibwork_cli_path, timeout_seconds=settings.gibwork_timeout)
    return PublicApiClient(
        base_url=settings.gibwork_base_url,
        timeout_seconds=settings.gibwork_timeout,
        max_retries=settings.gibwork_retries,
        request_interval_seconds=settings.gibwork_request_interval,
        api_key=settings.gibwork_api_key,
    )

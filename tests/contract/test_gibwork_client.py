"""Contract tests: HTTP adapter behaviour against a mocked transport."""

from __future__ import annotations

import json

import pytest
import requests

from bountypilot.integrations.gibwork import client as client_module
from bountypilot.integrations.gibwork.client import OfficialCliBridge, PublicApiClient
from bountypilot.integrations.gibwork.exceptions import (
    GibworkAuthenticationRequired,
    GibworkInvalidResponse,
    GibworkNotFound,
    GibworkRateLimited,
    GibworkUnavailable,
)
from tests.conftest import FIXTURE_EXPLORE, HACKATHON_BOUNTY_ID


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text or (json.dumps(payload) if payload is not None else "")

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def _client(**kwargs) -> PublicApiClient:
    defaults = dict(request_interval_seconds=0.0, max_retries=0)
    defaults.update(kwargs)
    return PublicApiClient(**defaults)


def test_explore_parses_and_paginates(monkeypatch):
    seen = {}

    def fake_get(url, params=None, headers=None, timeout=None, verify=None):
        seen["url"] = url
        seen["params"] = params
        return FakeResponse(payload=FIXTURE_EXPLORE)

    monkeypatch.setattr(client_module.requests, "get", fake_get)
    client = _client()
    page = client.explore(page=1, limit=5, search="hackathon")
    assert seen["url"].endswith("/explore")
    assert seen["params"]["search"] == "hackathon"
    assert seen["params"]["limit"] == 5
    assert len(page.results) == 2
    assert page.results[0].id == HACKATHON_BOUNTY_ID


def test_404_raises_not_found(monkeypatch):
    monkeypatch.setattr(client_module.requests, "get", lambda *a, **kw: FakeResponse(status_code=404))
    with pytest.raises(GibworkNotFound):
        _client()._get_json("/tasks/abc")


def test_401_raises_auth_required(monkeypatch):
    monkeypatch.setattr(client_module.requests, "get", lambda *a, **kw: FakeResponse(status_code=401))
    with pytest.raises(GibworkAuthenticationRequired):
        _client()._get_json("/explore")


def test_429_raises_rate_limited(monkeypatch):
    monkeypatch.setattr(client_module.requests, "get", lambda *a, **kw: FakeResponse(status_code=429))
    with pytest.raises(GibworkRateLimited):
        _client()._get_json("/explore")


def test_500_raises_unavailable(monkeypatch):
    monkeypatch.setattr(client_module.requests, "get", lambda *a, **kw: FakeResponse(status_code=503))
    with pytest.raises(GibworkUnavailable):
        _client()._get_json("/explore")


def test_invalid_json_raises_invalid_response(monkeypatch):
    monkeypatch.setattr(
        client_module.requests,
        "get",
        lambda *a, **kw: FakeResponse(status_code=200, text="not json{"),
    )
    with pytest.raises(GibworkInvalidResponse):
        _client()._get_json("/explore")


def test_network_error_raises_unavailable(monkeypatch):
    def boom(*a, **kw):
        raise requests.ConnectionError("no route")

    monkeypatch.setattr(client_module.requests, "get", boom)
    with pytest.raises(GibworkUnavailable):
        _client()._get_json("/explore")


def test_configured_key_retry_unauthenticated(monkeypatch):
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None, verify=None):
        calls.append(dict(headers or {}))
        if "Authorization" in (headers or {}):
            return FakeResponse(status_code=401)
        return FakeResponse(payload=FIXTURE_EXPLORE)

    monkeypatch.setattr(client_module.requests, "get", fake_get)
    client = _client(api_key="secret")
    page = client.explore()
    assert len(calls) == 2  # first with key, retry without
    assert client.auth_rejected is True
    assert page.total == 2
    assert "Authorization" not in calls[1]


def test_get_task_falls_back_to_explore(monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None, verify=None):
        if "/tasks/" in url:
            return FakeResponse(status_code=404)
        return FakeResponse(payload=FIXTURE_EXPLORE)

    monkeypatch.setattr(client_module.requests, "get", fake_get)
    client = _client()
    bounty = client.get_task(HACKATHON_BOUNTY_ID)
    assert bounty.id == HACKATHON_BOUNTY_ID


def test_get_task_not_found_anywhere(monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None, verify=None):
        if "/tasks/" in url:
            return FakeResponse(status_code=404)
        return FakeResponse(payload=FIXTURE_EXPLORE)

    monkeypatch.setattr(client_module.requests, "get", fake_get)
    with pytest.raises(GibworkNotFound):
        _client().get_task("00000000-0000-4000-8000-000000000000")


def test_no_authorization_header_without_key(monkeypatch):
    captured = {}

    def fake_get(url, params=None, headers=None, timeout=None, verify=None):
        captured["headers"] = headers
        return FakeResponse(payload=FIXTURE_EXPLORE)

    monkeypatch.setattr(client_module.requests, "get", fake_get)
    _client().explore()
    assert "Authorization" not in captured["headers"]


def test_deep_page_degrades_gracefully(monkeypatch):
    """Observed provider behaviour: page > 1 is 401 without a session; the
    adapter must return an honest empty page with a note, not an error."""

    def fake_get(url, params=None, headers=None, timeout=None, verify=None):
        params = params or {}
        if int(params.get("page", 1)) > 1:
            return FakeResponse(status_code=401)
        if params.get("limit") == 1:  # the page-1 total probe
            return FakeResponse(payload={"page": 1, "limit": 1, "total": 8, "lastPage": 8, "results": []})
        return FakeResponse(payload=FIXTURE_EXPLORE)

    monkeypatch.setattr(client_module.requests, "get", fake_get)
    page = _client().explore(page=2, limit=15)
    assert page.results == []
    assert page.note is not None
    assert "page 1 only" in page.note
    assert "8 bounties" in page.note
    assert page.to_dict()["note"] == page.note


def test_deep_page_degrades_without_total(monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None, verify=None):
        params = params or {}
        if int(params.get("page", 1)) > 1 or params.get("limit") == 1:
            return FakeResponse(status_code=401)
        return FakeResponse(payload=FIXTURE_EXPLORE)

    monkeypatch.setattr(client_module.requests, "get", fake_get)
    page = _client().explore(page=3, limit=15)
    assert page.results == []
    assert page.note is not None
    assert "requires an authenticated session" in page.note


def test_deep_page_401_still_raises_for_search(monkeypatch):
    """Page-1 requests (e.g. search) must keep failing loudly on auth errors."""
    monkeypatch.setattr(
        client_module.requests,
        "get",
        lambda *a, **kw: FakeResponse(status_code=401),
    )
    with pytest.raises(GibworkAuthenticationRequired):
        _client().explore(page=1, search="python")


def test_get_task_stops_pagination_at_auth_wall(monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None, verify=None):
        params = params or {}
        if "/tasks/" in url:
            return FakeResponse(status_code=404)
        if int(params.get("page", 1)) > 1:
            return FakeResponse(status_code=401)
        payload = dict(FIXTURE_EXPLORE)
        payload["lastPage"] = 3
        return FakeResponse(payload=payload)

    monkeypatch.setattr(client_module.requests, "get", fake_get)
    with pytest.raises(GibworkNotFound):
        _client().get_task("00000000-0000-4000-8000-000000000000")


# -- official CLI bridge (verified against @gibwork/cli 0.2.4) -----------------


class FakeCliResult:
    def __init__(self, exit_code=0, stdout="", stderr=""):
        self.ok = exit_code in (0, None)
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.timed_out = False


def _bridge(monkeypatch, results):
    """Bridge with run_command stubbed; `results` maps arg-tuple -> result."""
    calls = []

    def fake_run(argv, cwd=None, timeout_seconds=120, env_overrides=None):
        calls.append(list(argv))
        args = argv[1:-1] if argv[-1] == "--json" else argv[1:]  # drop cli_path / --json
        return results[tuple(args)]

    monkeypatch.setattr(client_module, "run_command", fake_run)
    return OfficialCliBridge("/usr/bin/env gibwork"), calls


def test_bridge_explore_uses_task_available(monkeypatch):
    payload = json.dumps({"ok": True, "tasks": FIXTURE_EXPLORE["results"]})
    bridge, calls = _bridge(
        monkeypatch,
        {("task", "available", "--page", "1", "--limit", "15"): FakeCliResult(stdout=payload)},
    )
    page = bridge.explore()
    assert calls[0][-1] == "--json"
    assert calls[0][1:7] == ["task", "available", "--page", "1", "--limit", "15"]
    assert len(page.results) == 2


def test_bridge_search_is_client_side(monkeypatch):
    payload = json.dumps({"ok": True, "tasks": FIXTURE_EXPLORE["results"]})
    bridge, _ = _bridge(
        monkeypatch,
        {("task", "available", "--page", "1", "--limit", "15"): FakeCliResult(stdout=payload)},
    )
    page = bridge.explore(search="hackathon")
    assert [b.title for b in page.results] == ["Gibwork Developer Hackathon Bounty"]


def test_bridge_maps_credential_error(monkeypatch):
    stderr = json.dumps({"ok": False, "error": {"code": "CREDENTIAL_ERROR", "message": "No wallet configured."}})
    bridge, _ = _bridge(
        monkeypatch,
        {("task", "available", "--page", "1", "--limit", "15"): FakeCliResult(exit_code=10, stderr=stderr)},
    )
    with pytest.raises(GibworkAuthenticationRequired, match="wallet"):
        bridge.explore()


def test_bridge_maps_server_error(monkeypatch):
    stderr = json.dumps({"ok": False, "error": {"code": "SERVER_ERROR", "message": "upstream unavailable"}})
    bridge, _ = _bridge(
        monkeypatch,
        {("task", "available", "--page", "1", "--limit", "15"): FakeCliResult(exit_code=10, stderr=stderr)},
    )
    with pytest.raises(GibworkUnavailable):
        bridge.explore()


def test_bridge_get_task(monkeypatch):
    task = dict(FIXTURE_EXPLORE["results"][0])
    payload = json.dumps({"ok": True, "task": task})
    bridge, calls = _bridge(
        monkeypatch,
        {("task", "get", HACKATHON_BOUNTY_ID): FakeCliResult(stdout=payload)},
    )
    bounty = bridge.get_task(HACKATHON_BOUNTY_ID)
    assert bounty.id == HACKATHON_BOUNTY_ID
    assert calls[0][1:3] == ["task", "get"]


def test_bridge_invalid_json(monkeypatch):
    bridge, _ = _bridge(
        monkeypatch,
        {("task", "available", "--page", "1", "--limit", "15"): FakeCliResult(stdout="not json{")},
    )
    with pytest.raises(GibworkInvalidResponse):
        bridge.explore()


def test_bridge_version(monkeypatch):
    bridge, _ = _bridge(monkeypatch, {("--version",): FakeCliResult(stdout="0.2.4\n")})
    assert bridge.version() == "0.2.4"


def test_bridge_health_reports_wallet_gap(monkeypatch):
    stderr = json.dumps({"ok": False, "error": {"code": "CREDENTIAL_ERROR", "message": "No wallet configured."}})
    bridge, calls = _bridge(
        monkeypatch,
        {
            ("--version",): FakeCliResult(stdout="0.2.4\n"),
            ("task", "available", "--page", "1", "--limit", "1"): FakeCliResult(exit_code=10, stderr=stderr),
        },
    )
    health = bridge.health()
    assert health["reachable"] is True
    assert health["authenticated"] is False
    assert "wallet" in health["note"]
    assert calls[1][1:7] == ["task", "available", "--page", "1", "--limit", "1"]


def test_bridge_health_listing_ok(monkeypatch):
    payload = json.dumps({"ok": True, "tasks": FIXTURE_EXPLORE["results"]})
    bridge, _ = _bridge(
        monkeypatch,
        {
            ("--version",): FakeCliResult(stdout="0.2.4\n"),
            ("task", "available", "--page", "1", "--limit", "1"): FakeCliResult(stdout=payload),
        },
    )
    health = bridge.health()
    assert health["listing_total"] == 2
    assert health["authenticated"] is True


def test_bridge_capabilities_document_limits():
    caps = OfficialCliBridge("/usr/bin/env gibwork").capabilities()
    assert caps["unsupported"]["server_side_search"]
    assert caps["unsupported"]["unauthenticated_listing"]


def test_failover_adopts_alternate_host(monkeypatch):
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None, verify=None):
        calls.append(url)
        if url.startswith("https://api.gib.work"):
            raise requests.ConnectionError("no route")
        return FakeResponse(payload=FIXTURE_EXPLORE)

    monkeypatch.setattr(client_module.requests, "get", fake_get)
    client = _client()
    page = client.explore(page=1, limit=5)
    assert client.base_url == "https://api2.gib.work"
    assert "unreachable" in (client.failover_note or "")
    assert calls[-1].startswith("https://api2.gib.work")
    assert len(page.results) == 2


def test_failover_both_hosts_down(monkeypatch):
    def boom(*a, **kw):
        raise requests.ConnectionError("no route")

    monkeypatch.setattr(client_module.requests, "get", boom)
    client = _client()
    with pytest.raises(GibworkUnavailable) as excinfo:
        client.explore(page=1, limit=5)
    assert "api2.gib.work" in excinfo.value.message
    assert client.base_url == "https://api.gib.work"


def test_failover_not_attempted_for_custom_base_url(monkeypatch):
    calls = []

    def boom(url, *a, **kw):
        calls.append(url)
        raise requests.ConnectionError("no route")

    monkeypatch.setattr(client_module.requests, "get", boom)
    client = _client(base_url="https://proxy.example.com")
    with pytest.raises(GibworkUnavailable):
        client.explore(page=1, limit=5)
    assert all(url.startswith("https://proxy.example.com") for url in calls)


def test_failover_happens_once_per_session(monkeypatch):
    calls = []

    def fake_get(url, *a, **kw):
        calls.append(url)
        if url.startswith("https://api.gib.work"):
            raise requests.ConnectionError("no route")
        return FakeResponse(payload=FIXTURE_EXPLORE)

    monkeypatch.setattr(client_module.requests, "get", fake_get)
    client = _client()
    client.explore(page=1, limit=5)
    client.explore(page=1, limit=5)
    primary_calls = [url for url in calls if url.startswith("https://api.gib.work")]
    assert len(primary_calls) == 1  # no repeated attempts against the dead host

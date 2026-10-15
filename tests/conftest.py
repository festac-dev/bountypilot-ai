"""Shared fixtures: isolated data directory and a fake Gibwork client."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from bountypilot.core.models import Bounty
from bountypilot.integrations.gibwork.client import ExplorePage

# Captured from the public Gibwork listing (real public data, used as a fixture).
FIXTURE_EXPLORE: dict = {
    "page": 1,
    "limit": 15,
    "total": 2,
    "lastPage": 1,
    "results": [
        {
            "id": "1052f22d-3f87-4b1d-b0d7-71a60679e7fa",
            "title": "Gibwork Developer Hackathon Bounty",
            "content": (
                "Join this bounty to create a new non-web-app use case. Requirements: "
                "The bounty must use Gibwork SDK, CLI, or MCP as a core part of the implementation. "
                "The bounty must not be a web app. The submission must include clear setup "
                "instructions. What to Submit: A public GitHub repository URL with all source code "
                "and a README. Screenshots of the project running."
            ),
            "deadline": "2026-10-30T04:00:00.000Z",
            "tags": ["Development"],
            "status": "CREATED",
            "isOpen": True,
            "remainingAmount": 1000,
            "asset": {"symbol": "USDC", "price": 1000, "decimals": 6},
            "user": {"username": "gibwork"},
        },
        {
            "id": "5f073804-1111-4d05-8f04-1c92dbee0002",
            "title": "Create a UGC Video Bounty",
            "content": "Create a short video about the product. Requirements: original content only.",
            "deadline": "2026-11-27T04:00:00.000Z",
            "tags": ["Social Media"],
            "status": "CREATED",
            "isOpen": True,
            "remainingAmount": 300,
            "asset": {"symbol": "USDC", "price": 300, "decimals": 6},
            "user": {"username": "creator"},
        },
    ],
}

HACKATHON_BOUNTY_ID = "1052f22d-3f87-4b1d-b0d7-71a60679e7fa"


class FakeGibworkClient:
    """Test double implementing the same interface as the real client."""

    mode = "public_api"

    def __init__(self, data: dict | None = None, fail: bool = False):
        self.data = data or FIXTURE_EXPLORE
        self.fail = fail
        self.explore_calls = 0
        self.detail_calls = 0

    def explore(self, page=1, limit=15, search="", tags=None):
        self.explore_calls += 1
        if self.fail:
            from bountypilot.integrations.gibwork.exceptions import GibworkUnavailable

            raise GibworkUnavailable("simulated outage")
        results = self.data["results"]
        if search:
            results = [r for r in results if search.lower() in r["title"].lower()]
        if tags:
            results = [r for r in results if any(t in r["tags"] for t in tags)]
        bounties = [Bounty.from_api(r) for r in results]
        return ExplorePage(bounties, page=page, limit=limit, total=len(bounties), last_page=1)

    def get_task(self, bounty_id):
        self.detail_calls += 1
        if self.fail:
            from bountypilot.integrations.gibwork.exceptions import GibworkUnavailable

            raise GibworkUnavailable("simulated outage")
        for raw in self.data["results"]:
            if raw["id"] == bounty_id.lower():
                return Bounty.from_api(raw)
        from bountypilot.integrations.gibwork.exceptions import GibworkNotFound

        raise GibworkNotFound(f"Bounty {bounty_id} not found.")

    def health(self):
        return {
            "reachable": not self.fail,
            "checked_at": "2026-10-13T00:00:00Z",
            "listing_total": self.data["total"],
            "auth_state": "unauthenticated",
        }

    def version(self):
        return "fake-1.0"

    def capabilities(self):
        return {"mode": self.mode, "supported": {}, "unsupported": {}}


@pytest.fixture
def data_dir(tmp_path):
    directory = tmp_path / "data"
    directory.mkdir()
    return str(directory)


@pytest.fixture
def fake_client():
    return FakeGibworkClient()


@pytest.fixture
def runner(data_dir, fake_client, monkeypatch) -> CliRunner:
    """CLI runner: isolated data dir via --config, fake client via create_client."""
    import bountypilot.services.container as container

    monkeypatch.setattr(container, "create_client", lambda settings: fake_client)
    return CliRunner()


@pytest.fixture
def app():
    from bountypilot.cli import build_app

    return build_app()


@pytest.fixture
def args_factory(data_dir):
    """Build argv with the isolated --config dir first."""

    def factory(*argv: str, json_mode: bool = False) -> list[str]:
        args = ["--config", data_dir]
        if json_mode:
            args.append("--json")
        return args + list(argv)

    return factory

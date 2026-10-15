"""Opt-in live integration test against the real Gibwork public API.

Run only when explicitly requested:  BOUNTYPILOT_LIVE_TESTS=1 pytest tests/integration/test_live_gibwork.py
Never runs in CI (CI uses the fake client so no credentials are needed).
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("BOUNTYPILOT_LIVE_TESTS") != "1",
    reason="Live Gibwork access is opt-in: set BOUNTYPILOT_LIVE_TESTS=1",
)


def test_live_explore():
    from bountypilot.integrations.gibwork.client import PublicApiClient

    client = PublicApiClient(request_interval_seconds=0.2)
    page = client.explore(limit=5)
    assert page.total >= 1
    assert all(b.id for b in page.results)
    assert all(b.title for b in page.results)


def test_live_health_and_get_task():
    from bountypilot.integrations.gibwork.client import PublicApiClient

    client = PublicApiClient(request_interval_seconds=0.2)
    health = client.health()
    assert health["reachable"] is True
    bounty = client.get_task("1052f22d-3f87-4b1d-b0d7-71a60679e7fa")
    assert bounty.title == "Gibwork Developer Hackathon Bounty"
    assert bounty.reward_symbol == "USDC"

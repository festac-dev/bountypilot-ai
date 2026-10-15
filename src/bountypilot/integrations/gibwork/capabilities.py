"""Verified capability map for the configured Gibwork integration."""

from __future__ import annotations

from typing import Any

from bountypilot.integrations.gibwork.client import GibworkClient

# Honest status labels (spec section: capability labelling).
IMPLEMENTED_TESTED = "Implemented and tested"
IMPLEMENTED = "Implemented"
AWAITING_CREDENTIALS = "Implemented, awaiting credentials"
PARTIAL = "Partially supported"
UNSUPPORTED = "Unsupported by the provider"
NOT_IMPLEMENTED = "Not implemented"


def describe(client: GibworkClient) -> dict[str, Any]:
    """Return the capability matrix with exact status labels."""
    caps = client.capabilities()
    base: dict[str, Any] = {
        "integration_mode": client.mode,
        "version": client.version(),
        "operations": {
            "bounty list (explore listing)": IMPLEMENTED_TESTED,
            "bounty search (server-side search)": IMPLEMENTED,
            "bounty show (single bounty)": IMPLEMENTED,
            "gibwork test (read-only health check)": IMPLEMENTED_TESTED,
            "pagination parameters": PARTIAL,
            "bounty creation": UNSUPPORTED,
            "submission upload": UNSUPPORTED,
            "wallet authentication": UNSUPPORTED,
            "user account access": UNSUPPORTED,
        },
        "adapter_reported": caps,
        "notes": [
            "Read-only integration by design; writes on Gibwork require on-chain "
            "Solana wallet transactions which are out of scope and unsafe to automate.",
            "Without an authenticated session, deep pagination may return HTTP 401; "
            "page 1 of the public listing works unauthenticated.",
        ],
    }
    if client.mode == "official_cli":
        base["operations"]["official CLI delegation"] = AWAITING_CREDENTIALS
    return base

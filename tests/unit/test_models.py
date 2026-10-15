"""Unit tests for core models and validation."""

from __future__ import annotations

import pytest

from bountypilot.core import validation
from bountypilot.core.models import Bounty
from bountypilot.exceptions import SecurityPolicyError, ValidationError
from tests.conftest import FIXTURE_EXPLORE


def test_from_api_builds_valid_model():
    bounty = Bounty.from_api(FIXTURE_EXPLORE["results"][0])
    assert bounty.id == "1052f22d-3f87-4b1d-b0d7-71a60679e7fa"
    assert bounty.reward_amount == 1000.0
    assert bounty.reward_symbol == "USDC"
    assert bounty.remaining_amount == 1000.0
    assert bounty.is_open is True
    assert bounty.origin == "provider"


def test_from_api_tolerates_missing_fields():
    bounty = Bounty.from_api({"id": FIXTURE_EXPLORE["results"][0]["id"]})
    assert bounty.title == "(untitled)"
    assert bounty.reward_amount is None
    assert bounty.deadline is None


def test_from_api_rejects_invalid_id():
    with pytest.raises(ValueError):
        Bounty.from_api({"id": "not-a-uuid"})


def test_bounty_id_validation():
    assert validation.bounty_id("1052F22D-3F87-4B1D-B0D7-71A60679E7FA") == "1052f22d-3f87-4b1d-b0d7-71a60679e7fa"
    with pytest.raises(ValidationError):
        validation.bounty_id("../etc/passwd")
    with pytest.raises(ValidationError):
        validation.bounty_id("")


def test_safe_output_path_blocks_traversal(tmp_path):
    inside = validation.safe_output_path(tmp_path, "sub/file.txt")
    assert str(inside).startswith(str(tmp_path))
    with pytest.raises(SecurityPolicyError):
        validation.safe_output_path(tmp_path, "../outside.txt")
    with pytest.raises(SecurityPolicyError):
        validation.safe_output_path(tmp_path, "/etc/passwd")


def test_safe_relative_name():
    assert validation.safe_relative_name("readme.md") == "readme.md"
    with pytest.raises(SecurityPolicyError):
        validation.safe_relative_name("..")
    with pytest.raises(SecurityPolicyError):
        validation.safe_relative_name("a/b")


def test_optional_int():
    assert validation.optional_int("5", "x") == 5
    assert validation.optional_int("", "x") is None
    assert validation.optional_int(None, "x") is None
    with pytest.raises(ValidationError):
        validation.optional_int("abc", "x")

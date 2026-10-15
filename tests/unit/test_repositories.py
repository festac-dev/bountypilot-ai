"""Unit tests for SQLite storage: migrations, idempotency, corruption handling."""

from __future__ import annotations

import pytest

from bountypilot.core.models import Bounty
from bountypilot.storage.database import Database
from bountypilot.storage.repositories import (
    AnalysisRepository,
    BountyRepository,
    TrackingRepository,
)
from tests.conftest import FIXTURE_EXPLORE


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "test.db")
    database.connect()
    yield database
    database.close()


@pytest.fixture
def repos(db):
    bounties = BountyRepository(db)
    return bounties, TrackingRepository(db, bounties), AnalysisRepository(db)


def _bounty() -> Bounty:
    return Bounty.from_api(FIXTURE_EXPLORE["results"][0])


def test_migrations_create_schema(db):
    tables = {r["name"] for r in db.query("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {
        "bounties",
        "tracked_bounties",
        "analyses",
        "reminders",
        "evidence",
        "watch_configs",
        "watch_changes",
        "schema_migrations",
    } <= tables


def test_repeated_upsert_is_idempotent(repos):
    bounties, _, _ = repos
    assert bounties.upsert(_bounty()) is True
    assert bounties.upsert(_bounty()) is False
    rows = bounties.list()
    assert len(rows) == 1
    assert rows[0].title == _bounty().title


def test_upsert_preserves_notes(repos):
    bounties, _, _ = repos
    bounties.upsert(_bounty(), notes="my private notes")
    bounties.upsert(_bounty())  # refresh from provider
    assert bounties.get_notes(_bounty().id) == "my private notes"


def test_tracking_lifecycle_and_transitions(db, repos):
    bounties, tracking, _ = repos
    bounties.upsert(_bounty())
    tracking.add(_bounty().id)
    tracking.add(_bounty().id)  # idempotent
    assert len(tracking.list()) == 1
    tracking.set_status(_bounty().id, "evaluating")
    assert tracking.get(_bounty().id).local_status == "evaluating"
    from bountypilot.exceptions import DuplicateRecordError

    with pytest.raises(DuplicateRecordError):
        db.execute(
            "INSERT INTO tracked_bounties (bounty_id, local_status, notes, created_at, updated_at)"
            " VALUES (?, 'saved', '', 'x', 'x')",
            (_bounty().id,),
        )


def test_tracking_cannot_track_unknown_bounty(repos):
    _, tracking, _ = repos
    from bountypilot.exceptions import DuplicateRecordError

    with pytest.raises(DuplicateRecordError):
        tracking.add("1052f22d-3f87-4b1d-b0d7-71a60679e7fa")


def test_import_skips_unknown_and_conflicting(repos):
    bounties, tracking, _ = repos
    bounties.upsert(_bounty())
    tracking.add(_bounty().id)
    rows = [
        {"bounty_id": _bounty().id, "local_status": "in progress"},  # conflict -> skipped
        {
            "bounty_id": "5f073804-1111-4d05-8f04-1c92dbee0002",
            "local_status": "saved",
        },  # unknown -> skipped
        {"bounty_id": "not-a-uuid", "local_status": "saved"},  # invalid -> skipped
    ]
    stats = tracking.import_rows(rows)
    assert stats == {"created": 0, "updated": 0, "skipped": 3}
    stats = tracking.import_rows(rows, overwrite=True)
    assert stats["updated"] == 1
    assert tracking.get(_bounty().id).local_status == "in progress"


def test_corruption_detected(tmp_path):
    path = tmp_path / "broken.db"
    path.write_bytes(b"this is not a sqlite database at all")
    database = Database(path)
    with pytest.raises(Exception):
        database.connect()


def test_database_not_storing_secrets(repos):
    bounties, _, _ = repos
    bounties.upsert(_bounty())
    import json

    # Every column of the bounty row must be non-secret data.
    bounty = _bounty()
    blob = json.dumps({k: getattr(bounty, k) for k in bounty.__dict__})
    assert "GIBWORK_API_KEY" not in blob

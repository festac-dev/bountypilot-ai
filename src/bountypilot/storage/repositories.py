"""Repositories: all SQL lives here, behind the service layer."""

from __future__ import annotations

import json
from typing import Any, List, Optional

from bountypilot.core import models as m
from bountypilot.exceptions import DuplicateRecordError
from bountypilot.storage.database import Database


class BountyRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    @staticmethod
    def _row_to_bounty(row: Any) -> m.Bounty:
        return m.Bounty(
            id=row["id"],
            title=row["title"],
            content=row["content"],
            deadline=row["deadline"],
            tags=json.loads(row["tags"] or "[]"),
            status=row["status"],
            is_open=bool(row["is_open"]),
            reward_amount=row["reward_amount"],
            reward_symbol=row["reward_symbol"],
            remaining_amount=row["remaining_amount"],
            poster_username=row["poster_username"],
            url=row["url"],
            origin=row["origin"],
            retrieved_at=row["retrieved_at"],
        )

    def upsert(self, bounty: m.Bounty, notes: str = "") -> bool:
        """Store/refresh a bounty snapshot. Returns True when a new row was created."""
        existing = self.db.query_one("SELECT notes FROM bounties WHERE id=?", (bounty.id,))
        if existing is None:
            self.db.execute(
                "INSERT INTO bounties (id, title, content, deadline, tags, status, is_open,"
                " reward_amount, reward_symbol, remaining_amount, poster_username, url,"
                " origin, retrieved_at, notes) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    bounty.id,
                    bounty.title,
                    bounty.content,
                    bounty.deadline,
                    json.dumps(bounty.tags),
                    bounty.status,
                    int(bounty.is_open),
                    bounty.reward_amount,
                    bounty.reward_symbol,
                    bounty.remaining_amount,
                    bounty.poster_username,
                    bounty.url,
                    bounty.origin,
                    bounty.retrieved_at,
                    notes,
                ),
            )
            return True
        self.db.execute(
            "UPDATE bounties SET title=?, content=?, deadline=?, tags=?, status=?, is_open=?,"
            " reward_amount=?, reward_symbol=?, remaining_amount=?, poster_username=?, url=?,"
            " origin=?, retrieved_at=?, notes=? WHERE id=?",
            (
                bounty.title,
                bounty.content,
                bounty.deadline,
                json.dumps(bounty.tags),
                bounty.status,
                int(bounty.is_open),
                bounty.reward_amount,
                bounty.reward_symbol,
                bounty.remaining_amount,
                bounty.poster_username,
                bounty.url,
                bounty.origin,
                bounty.retrieved_at,
                notes or (existing["notes"] or ""),
                bounty.id,
            ),
        )
        return False

    def get(self, bounty_id: str) -> Optional[m.Bounty]:
        row = self.db.query_one("SELECT * FROM bounties WHERE id=?", (bounty_id.lower(),))
        return self._row_to_bounty(row) if row else None

    def get_notes(self, bounty_id: str) -> str:
        row = self.db.query_one("SELECT notes FROM bounties WHERE id=?", (bounty_id.lower(),))
        return row["notes"] if row and row["notes"] else ""

    def list(self, search: str = "", open_only: bool = False) -> List[m.Bounty]:
        sql = "SELECT * FROM bounties WHERE 1=1"
        params: list[Any] = []
        if search:
            sql += " AND (title LIKE ? OR content LIKE ?)"
            like = f"%{search}%"
            params += [like, like]
        if open_only:
            sql += " AND is_open = 1"
        sql += " ORDER BY retrieved_at DESC"
        return [self._row_to_bounty(r) for r in self.db.query(sql, tuple(params))]

    def set_notes(self, bounty_id: str, notes: str) -> None:
        self.db.execute("UPDATE bounties SET notes=? WHERE id=?", (notes, bounty_id.lower()))


class TrackingRepository:
    IMPORT_STATUSES = frozenset({"saved", "evaluating", "planned", "in progress", "blocked", "completed", "abandoned"})

    def __init__(self, db: Database, bounty_repo: BountyRepository) -> None:
        self.db = db
        self.bounties = bounty_repo

    def add(self, bounty_id: str, notes: str = "") -> None:
        """Track a bounty; idempotent (re-adding refreshes notes, never duplicates)."""
        if self.bounties.get(bounty_id) is None:
            raise DuplicateRecordError(
                f"Bounty {bounty_id} is not stored locally; run 'bountypilot bounty show {bounty_id}' first."
            )
        if self.get(bounty_id):
            if notes:
                self.set_notes(bounty_id, notes)
            return
        now = m.utc_now_iso()
        self.db.execute(
            "INSERT INTO tracked_bounties (bounty_id, local_status, notes, created_at, updated_at) VALUES (?,?,?,?,?)",
            (bounty_id.lower(), "saved", notes, now, now),
        )

    def get(self, bounty_id: str) -> Optional[m.TrackedBounty]:
        row = self.db.query_one("SELECT * FROM tracked_bounties WHERE bounty_id=?", (bounty_id.lower(),))
        if not row:
            return None
        return m.TrackedBounty(
            bounty_id=row["bounty_id"],
            local_status=row["local_status"],
            notes=row["notes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def list(self) -> List[m.TrackedBounty]:
        rows = self.db.query("SELECT * FROM tracked_bounties ORDER BY created_at DESC")
        return [
            m.TrackedBounty(
                bounty_id=r["bounty_id"],
                local_status=r["local_status"],
                notes=r["notes"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ]

    def set_status(self, bounty_id: str, status: str) -> None:
        self.db.execute(
            "UPDATE tracked_bounties SET local_status=?, updated_at=? WHERE bounty_id=?",
            (status, m.utc_now_iso(), bounty_id.lower()),
        )

    def set_notes(self, bounty_id: str, notes: str) -> None:
        self.db.execute(
            "UPDATE tracked_bounties SET notes=?, updated_at=? WHERE bounty_id=?",
            (notes, m.utc_now_iso(), bounty_id.lower()),
        )

    def remove(self, bounty_id: str) -> bool:
        cur = self.db.execute("DELETE FROM tracked_bounties WHERE bounty_id=?", (bounty_id.lower(),))
        return cur.rowcount > 0

    def export_rows(self) -> List[dict[str, Any]]:
        return [t.to_dict() for t in self.list()]

    def import_rows(self, rows: List[dict], overwrite: bool = False) -> dict[str, int]:
        """Safe import: never silently overwrites conflicting data."""
        created = updated = skipped = 0
        for row in rows:
            bounty_id = str(row.get("bounty_id", "")).strip().lower()
            if not bounty_id:
                skipped += 1
                continue
            status = str(row.get("local_status", "saved")).strip().lower()
            if status not in self.IMPORT_STATUSES:
                skipped += 1
                continue
            if self.bounties.get(bounty_id) is None:
                skipped += 1
                continue
            existing = self.get(bounty_id)
            if existing and not overwrite:
                skipped += 1
                continue
            if existing:
                self.set_status(bounty_id, status)
                if row.get("notes"):
                    self.set_notes(bounty_id, str(row["notes"]))
                updated += 1
            else:
                now = m.utc_now_iso()
                self.db.execute(
                    "INSERT INTO tracked_bounties (bounty_id, local_status, notes, created_at, updated_at)"
                    " VALUES (?,?,?,?,?)",
                    (bounty_id, status, str(row.get("notes", "")), now, now),
                )
                created += 1
        return {"created": created, "updated": updated, "skipped": skipped}


class AnalysisRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def save(self, analysis: m.Analysis) -> str:
        import uuid

        analysis_id = str(uuid.uuid4())
        self.db.execute(
            "INSERT INTO analyses (id, bounty_id, provider, payload, origin, created_at) VALUES (?,?,?,?,?,?)",
            (
                analysis_id,
                analysis.bounty_id,
                analysis.provider,
                json.dumps(analysis.to_dict()),
                analysis.origin,
                analysis.created_at,
            ),
        )
        return analysis_id

    def latest_for(self, bounty_id: str) -> Optional[dict[str, Any]]:
        row = self.db.query_one(
            "SELECT payload FROM analyses WHERE bounty_id=? ORDER BY created_at DESC LIMIT 1",
            (bounty_id.lower(),),
        )
        return json.loads(row["payload"]) if row else None

    def list_for(self, bounty_id: str) -> List[dict[str, Any]]:
        rows = self.db.query(
            "SELECT payload FROM analyses WHERE bounty_id=? ORDER BY created_at DESC",
            (bounty_id.lower(),),
        )
        return [json.loads(r["payload"]) for r in rows]


class ReminderRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, reminder: m.Reminder) -> str:
        import uuid

        reminder_id = str(uuid.uuid4())
        self.db.execute(
            "INSERT INTO reminders (id, bounty_id, message, deadline, lead_time_hours, created_at)"
            " VALUES (?,?,?,?,?,?)",
            (
                reminder_id,
                reminder.bounty_id or None,
                reminder.message,
                reminder.deadline,
                reminder.lead_time_hours,
                reminder.created_at,
            ),
        )
        return reminder_id

    def list(self) -> List[m.Reminder]:
        rows = self.db.query("SELECT * FROM reminders ORDER BY created_at DESC")
        return [
            m.Reminder(
                bounty_id=r["bounty_id"] or "",
                message=r["message"],
                deadline=r["deadline"],
                lead_time_hours=r["lead_time_hours"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def remove(self, index_or_id: str) -> bool:
        reminders = self.list()
        target = None
        if index_or_id.isdigit() and 1 <= int(index_or_id) <= len(reminders):
            target = reminders[int(index_or_id) - 1]
        for r in reminders:
            if r.created_at == index_or_id or (r.bounty_id and r.bounty_id == index_or_id):
                target = r
                break
        if target is None:
            return False
        cur = self.db.execute(
            "DELETE FROM reminders WHERE bounty_id IS ? AND message=? AND created_at=?",
            (target.bounty_id or None, target.message, target.created_at),
        )
        return cur.rowcount > 0


class EvidenceRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, evidence: m.Evidence) -> str:
        import uuid

        evidence_id = str(uuid.uuid4())
        self.db.execute(
            "INSERT INTO evidence (id, kind, description, content_path, content_hash,"
            " bounty_id, origin, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (
                evidence_id,
                evidence.kind,
                evidence.description,
                evidence.content_path,
                evidence.content_hash,
                evidence.bounty_id or None,
                evidence.origin,
                evidence.created_at,
            ),
        )
        return evidence_id

    def list(self) -> List[m.Evidence]:
        rows = self.db.query("SELECT * FROM evidence ORDER BY created_at DESC")
        return [
            m.Evidence(
                kind=r["kind"],
                description=r["description"],
                content_path=r["content_path"],
                content_hash=r["content_hash"],
                bounty_id=r["bounty_id"] or "",
                created_at=r["created_at"],
                origin=r["origin"],
            )
            for r in rows
        ]


class WatchRepository:
    def __init__(self, db: Database, bounty_repo: BountyRepository) -> None:
        self.db = db
        self.bounties = bounty_repo

    def add(self, bounty_id: str, interval_seconds: int) -> None:
        if self.bounties.get(bounty_id) is None:
            raise DuplicateRecordError(f"Bounty {bounty_id} is not stored locally.")
        if self.get(bounty_id):
            return
        import uuid

        self.db.execute(
            "INSERT INTO watch_configs (id, bounty_id, interval_seconds, created_at) VALUES (?,?,?,?)",
            (str(uuid.uuid4()), bounty_id.lower(), interval_seconds, m.utc_now_iso()),
        )

    def get(self, bounty_id: str) -> Optional[dict[str, Any]]:
        row = self.db.query_one(
            "SELECT bounty_id, interval_seconds, created_at FROM watch_configs WHERE bounty_id=?",
            (bounty_id.lower(),),
        )
        return dict(row) if row else None

    def list(self) -> List[dict[str, Any]]:
        return [
            dict(r)
            for r in self.db.query(
                "SELECT bounty_id, interval_seconds, created_at FROM watch_configs ORDER BY created_at"
            )
        ]

    def remove(self, bounty_id: str) -> bool:
        cur = self.db.execute("DELETE FROM watch_configs WHERE bounty_id=?", (bounty_id.lower(),))
        return cur.rowcount > 0

    def record_change(self, bounty_id: str, field: str, old: Any, new: Any) -> None:
        self.db.execute(
            "INSERT INTO watch_changes (bounty_id, field, old_value, new_value, changed_at) VALUES (?,?,?,?,?)",
            (
                bounty_id.lower(),
                field,
                str(old) if old is not None else None,
                str(new) if new is not None else None,
                m.utc_now_iso(),
            ),
        )

    def changes_for(self, bounty_id: str) -> List[dict[str, Any]]:
        return [
            dict(r)
            for r in self.db.query(
                "SELECT field, old_value, new_value, changed_at FROM watch_changes"
                " WHERE bounty_id=? ORDER BY changed_at DESC",
                (bounty_id.lower(),),
            )
        ]

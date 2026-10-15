"""SQLite storage with ordered migrations, transactions and integrity handling."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Optional

from bountypilot.exceptions import DatabaseCorruptionError, StorageError
from bountypilot.logging_config import get_logger
from bountypilot.security.path_validation import ensure_directory

log = get_logger("bountypilot.storage")

MIGRATIONS: list[tuple[int, str]] = [
    (
        1,
        """
        CREATE TABLE bounties (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            content TEXT NOT NULL DEFAULT '',
            deadline TEXT,
            tags TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL DEFAULT '',
            is_open INTEGER NOT NULL DEFAULT 1,
            reward_amount REAL,
            reward_symbol TEXT NOT NULL DEFAULT '',
            remaining_amount REAL,
            poster_username TEXT NOT NULL DEFAULT '',
            url TEXT NOT NULL DEFAULT '',
            origin TEXT NOT NULL DEFAULT 'provider',
            retrieved_at TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX idx_bounties_open ON bounties(is_open);
        CREATE INDEX idx_bounties_title ON bounties(title);

        CREATE TABLE tracked_bounties (
            bounty_id TEXT PRIMARY KEY REFERENCES bounties(id) ON DELETE CASCADE,
            local_status TEXT NOT NULL DEFAULT 'saved',
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX idx_tracked_status ON tracked_bounties(local_status);

        CREATE TABLE analyses (
            id TEXT PRIMARY KEY,
            bounty_id TEXT NOT NULL REFERENCES bounties(id) ON DELETE CASCADE,
            provider TEXT NOT NULL,
            payload TEXT NOT NULL,
            origin TEXT NOT NULL DEFAULT 'ai_estimate',
            created_at TEXT NOT NULL
        );
        CREATE INDEX idx_analyses_bounty ON analyses(bounty_id);

        CREATE TABLE reminders (
            id TEXT PRIMARY KEY,
            bounty_id TEXT REFERENCES bounties(id) ON DELETE CASCADE,
            message TEXT NOT NULL,
            deadline TEXT,
            lead_time_hours INTEGER NOT NULL DEFAULT 48,
            created_at TEXT NOT NULL
        );
        CREATE INDEX idx_reminders_bounty ON reminders(bounty_id);

        CREATE TABLE evidence (
            id TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            description TEXT NOT NULL,
            content_path TEXT NOT NULL DEFAULT '',
            content_hash TEXT NOT NULL DEFAULT '',
            bounty_id TEXT,
            origin TEXT NOT NULL DEFAULT 'verified_run',
            created_at TEXT NOT NULL
        );
        CREATE INDEX idx_evidence_bounty ON evidence(bounty_id);

        CREATE TABLE watch_configs (
            id TEXT PRIMARY KEY,
            bounty_id TEXT NOT NULL UNIQUE REFERENCES bounties(id) ON DELETE CASCADE,
            interval_seconds INTEGER NOT NULL DEFAULT 300,
            created_at TEXT NOT NULL
        );

        CREATE TABLE watch_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bounty_id TEXT NOT NULL REFERENCES bounties(id) ON DELETE CASCADE,
            field TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            changed_at TEXT NOT NULL
        );
        CREATE INDEX idx_watch_changes_bounty ON watch_changes(bounty_id);
        """,
    ),
]


class Database:
    """Connection management, migrations and transactions for the local store."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self) -> sqlite3.Connection:
        if self._conn is not None:
            return self._conn
        ensure_directory(self.path.parent, mode=0o700)
        try:
            conn = sqlite3.connect(str(self.path), timeout=15)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.Error as exc:
            raise StorageError(f"Cannot open database {self.path}: {exc}") from exc
        self._conn = conn
        self.migrate()
        return conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def migrate(self) -> None:
        conn = self.connect() if self._conn is None else self._conn
        try:
            with self.transaction():
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS schema_migrations ("
                    "version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
                )
                row = conn.execute("SELECT MAX(version) AS v FROM schema_migrations").fetchone()
                current = row["v"] or 0
                for version, script in MIGRATIONS:
                    if version <= current:
                        continue
                    log.info("applying migration %d", version)
                    conn.executescript(script)
                    conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))
        except sqlite3.DatabaseError as exc:
            raise DatabaseCorruptionError(
                f"Database at {self.path} could not be migrated: {exc}. "
                "Move the file away and run 'bountypilot init' to start fresh."
            ) from exc

    def transaction(self) -> sqlite3.Connection:
        if self._conn is None:
            self.connect()
        return self._conn  # type: ignore[return-value]

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        conn = self.transaction()
        try:
            cur = conn.execute(sql, params)
            conn.commit()
            return cur
        except sqlite3.IntegrityError as exc:
            conn.rollback()
            from bountypilot.exceptions import DuplicateRecordError

            raise DuplicateRecordError(str(exc)) from exc
        except sqlite3.Error as exc:
            conn.rollback()
            raise StorageError(f"Database operation failed: {exc}") from exc

    def query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        conn = self.transaction()
        try:
            return list(conn.execute(sql, params).fetchall())
        except sqlite3.Error as exc:
            raise StorageError(f"Database query failed: {exc}") from exc

    def query_one(self, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def __enter__(self) -> Database:
        self.connect()
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

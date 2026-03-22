"""SQLite backend for the memory subsystem.

Uses SQLite in WAL mode for concurrent-read performance and creates an FTS5
virtual table for full-text search.  Thread safety relies on SQLite's own
internal locking, plus ``check_same_thread=False`` so the connection can be
shared across threads.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from claudekit.errors import MemoryBackendError
from claudekit.memory._backends._base import AbstractBackend
from claudekit.memory._entry import MemoryEntry

logger = logging.getLogger(__name__)

_SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS memory_entries (
    key        TEXT    NOT NULL,
    value      TEXT    NOT NULL,
    scope      TEXT,
    created_at TEXT    NOT NULL,
    updated_at TEXT    NOT NULL,
    expires_at TEXT,
    metadata   TEXT    NOT NULL DEFAULT '{}',
    PRIMARY KEY (key, scope)
);

CREATE INDEX IF NOT EXISTS idx_memory_scope
    ON memory_entries(scope);

CREATE INDEX IF NOT EXISTS idx_memory_updated
    ON memory_entries(updated_at);
"""

_FTS_SCHEMA_SQL = """\
CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts
    USING fts5(key, value, content=memory_entries, content_rowid=rowid);

CREATE TRIGGER IF NOT EXISTS memory_ai AFTER INSERT ON memory_entries BEGIN
    INSERT INTO memory_fts(rowid, key, value)
        VALUES (new.rowid, new.key, new.value);
END;

CREATE TRIGGER IF NOT EXISTS memory_ad AFTER DELETE ON memory_entries BEGIN
    INSERT INTO memory_fts(memory_fts, rowid, key, value)
        VALUES ('delete', old.rowid, old.key, old.value);
END;

CREATE TRIGGER IF NOT EXISTS memory_au AFTER UPDATE ON memory_entries BEGIN
    INSERT INTO memory_fts(memory_fts, rowid, key, value)
        VALUES ('delete', old.rowid, old.key, old.value);
    INSERT INTO memory_fts(rowid, key, value)
        VALUES (new.rowid, new.key, new.value);
END;
"""

# How many writes between automatic expired-entry sweeps.
_CLEANUP_INTERVAL = 100


class SQLiteBackend(AbstractBackend):
    """Persist memory entries in a local SQLite database.

    Parameters
    ----------
    path:
        Location of the ``.db`` file.  Parent directories are created
        automatically.  Defaults to ``~/.claudekit/memory.db``.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        if path is None:
            path = Path.home() / ".claudekit" / "memory.db"
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

        self._write_count = 0
        self._write_lock = threading.Lock()

        self._conn = self._connect()
        self._ensure_schema()
        logger.debug("SQLiteBackend initialised at %s", self._path)

    # -- connection & schema --------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        """Open (or create) the database and enable WAL mode."""
        try:
            conn = sqlite3.connect(
                str(self._path),
                check_same_thread=False,
            )
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA foreign_keys=ON;")
            return conn
        except sqlite3.Error as exc:
            raise MemoryBackendError(
                f"Failed to open SQLite database at {self._path}: {exc}"
            ) from exc

    def _ensure_schema(self) -> None:
        """Create tables and FTS index if they do not exist."""
        try:
            cur = self._conn.cursor()
            cur.executescript(_SCHEMA_SQL)
            cur.executescript(_FTS_SCHEMA_SQL)
            self._conn.commit()
        except sqlite3.Error as exc:
            raise MemoryBackendError(
                f"Failed to initialise schema: {exc}"
            ) from exc

    # -- internal helpers -----------------------------------------------------

    def _maybe_cleanup(self) -> None:
        """Run an expired-entry sweep every ``_CLEANUP_INTERVAL`` writes."""
        self._write_count += 1
        if self._write_count % _CLEANUP_INTERVAL == 0:
            self._sweep_expired()

    def _sweep_expired(self) -> None:
        """Delete all entries whose ``expires_at`` is in the past."""
        now = datetime.now(timezone.utc).isoformat()
        try:
            cur = self._conn.execute(
                "DELETE FROM memory_entries WHERE expires_at IS NOT NULL "
                "AND expires_at <= ?",
                (now,),
            )
            self._conn.commit()
            if cur.rowcount:
                logger.debug("Swept %d expired entries.", cur.rowcount)
        except sqlite3.Error as exc:
            logger.warning("Expired-entry sweep failed: %s", exc)

    @staticmethod
    def _row_to_entry(row: tuple) -> MemoryEntry:  # noqa: ANN401
        """Convert a database row to a :class:`MemoryEntry`."""
        import json

        key, value, scope, created_at, updated_at, expires_at, metadata_json = row
        return MemoryEntry(
            key=key,
            value=value,
            scope=scope,
            created_at=datetime.fromisoformat(created_at),
            updated_at=datetime.fromisoformat(updated_at),
            expires_at=(
                datetime.fromisoformat(expires_at) if expires_at else None
            ),
            metadata=json.loads(metadata_json) if metadata_json else {},
        )

    # -- AbstractBackend implementation ---------------------------------------

    def save(self, entry: MemoryEntry) -> None:
        """Persist *entry* via INSERT OR REPLACE."""
        import json

        with self._write_lock:
            try:
                self._conn.execute(
                    "INSERT OR REPLACE INTO memory_entries "
                    "(key, value, scope, created_at, updated_at, expires_at, metadata) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        entry.key,
                        entry.value,
                        entry.scope,
                        entry.created_at.isoformat(),
                        entry.updated_at.isoformat(),
                        entry.expires_at.isoformat() if entry.expires_at else None,
                        json.dumps(entry.metadata, ensure_ascii=False),
                    ),
                )
                self._conn.commit()
                self._maybe_cleanup()
                logger.debug(
                    "Saved entry key=%r scope=%r", entry.key, entry.scope
                )
            except sqlite3.Error as exc:
                raise MemoryBackendError(
                    f"Failed to save entry key={entry.key!r}: {exc}"
                ) from exc

    def get(self, key: str, scope: str | None = None) -> MemoryEntry | None:
        """Return the entry for *(key, scope)* or ``None``."""
        try:
            if scope is None:
                row = self._conn.execute(
                    "SELECT key, value, scope, created_at, updated_at, "
                    "expires_at, metadata FROM memory_entries "
                    "WHERE key = ? AND scope IS NULL",
                    (key,),
                ).fetchone()
            else:
                row = self._conn.execute(
                    "SELECT key, value, scope, created_at, updated_at, "
                    "expires_at, metadata FROM memory_entries "
                    "WHERE key = ? AND scope = ?",
                    (key, scope),
                ).fetchone()
        except sqlite3.Error as exc:
            raise MemoryBackendError(
                f"Failed to get entry key={key!r}: {exc}"
            ) from exc

        if row is None:
            return None

        entry = self._row_to_entry(row)
        # Lazy expiry check.
        if (
            entry.expires_at is not None
            and entry.expires_at <= datetime.now(timezone.utc)
        ):
            return None
        return entry

    def search(
        self,
        query: str,
        scope: str | None = None,
        limit: int = 10,
    ) -> list[MemoryEntry]:
        """Full-text search via FTS5, falling back to LIKE for simple queries.

        The FTS5 index is tried first.  If the query contains no FTS
        operators and FTS returns nothing, a ``LIKE`` fallback ensures
        substring matches are still found.
        """
        now = datetime.now(timezone.utc).isoformat()
        results: list[MemoryEntry] = []

        # --- try FTS5 first ---
        try:
            fts_query = '"' + query.replace('"', '""') + '"'
            if scope is None:
                rows = self._conn.execute(
                    "SELECT e.key, e.value, e.scope, e.created_at, "
                    "e.updated_at, e.expires_at, e.metadata "
                    "FROM memory_entries e "
                    "JOIN memory_fts f ON e.rowid = f.rowid "
                    "WHERE memory_fts MATCH ? "
                    "AND (e.expires_at IS NULL OR e.expires_at > ?) "
                    "ORDER BY rank LIMIT ?",
                    (fts_query, now, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT e.key, e.value, e.scope, e.created_at, "
                    "e.updated_at, e.expires_at, e.metadata "
                    "FROM memory_entries e "
                    "JOIN memory_fts f ON e.rowid = f.rowid "
                    "WHERE memory_fts MATCH ? AND e.scope = ? "
                    "AND (e.expires_at IS NULL OR e.expires_at > ?) "
                    "ORDER BY rank LIMIT ?",
                    (fts_query, scope, now, limit),
                ).fetchall()
            results = [self._row_to_entry(r) for r in rows]
        except sqlite3.Error:
            logger.debug("FTS query failed; falling back to LIKE.")

        if results:
            return results

        # --- LIKE fallback ---
        try:
            like_param = f"%{query}%"
            if scope is None:
                rows = self._conn.execute(
                    "SELECT key, value, scope, created_at, updated_at, "
                    "expires_at, metadata FROM memory_entries "
                    "WHERE (key LIKE ? OR value LIKE ?) "
                    "AND (expires_at IS NULL OR expires_at > ?) "
                    "ORDER BY updated_at DESC LIMIT ?",
                    (like_param, like_param, now, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT key, value, scope, created_at, updated_at, "
                    "expires_at, metadata FROM memory_entries "
                    "WHERE scope = ? "
                    "AND (key LIKE ? OR value LIKE ?) "
                    "AND (expires_at IS NULL OR expires_at > ?) "
                    "ORDER BY updated_at DESC LIMIT ?",
                    (scope, like_param, like_param, now, limit),
                ).fetchall()
            results = [self._row_to_entry(r) for r in rows]
        except sqlite3.Error as exc:
            raise MemoryBackendError(
                f"Search failed for query={query!r}: {exc}"
            ) from exc

        return results

    def delete(self, key: str, scope: str | None = None) -> bool:
        """Delete the entry for *(key, scope)*."""
        with self._write_lock:
            try:
                if scope is None:
                    cur = self._conn.execute(
                        "DELETE FROM memory_entries WHERE key = ? AND scope IS NULL",
                        (key,),
                    )
                else:
                    cur = self._conn.execute(
                        "DELETE FROM memory_entries WHERE key = ? AND scope = ?",
                        (key, scope),
                    )
                self._conn.commit()
                deleted = cur.rowcount > 0
                if deleted:
                    logger.debug("Deleted key=%r scope=%r", key, scope)
                return deleted
            except sqlite3.Error as exc:
                raise MemoryBackendError(
                    f"Failed to delete key={key!r}: {exc}"
                ) from exc

    def list_entries(self, scope: str | None = None) -> list[MemoryEntry]:
        """Return all non-expired entries in *scope*, sorted by updated_at."""
        now = datetime.now(timezone.utc).isoformat()
        try:
            if scope is None:
                rows = self._conn.execute(
                    "SELECT key, value, scope, created_at, updated_at, "
                    "expires_at, metadata FROM memory_entries "
                    "WHERE (expires_at IS NULL OR expires_at > ?) "
                    "ORDER BY updated_at ASC",
                    (now,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT key, value, scope, created_at, updated_at, "
                    "expires_at, metadata FROM memory_entries "
                    "WHERE scope = ? "
                    "AND (expires_at IS NULL OR expires_at > ?) "
                    "ORDER BY updated_at ASC",
                    (scope, now),
                ).fetchall()
            return [self._row_to_entry(r) for r in rows]
        except sqlite3.Error as exc:
            raise MemoryBackendError(
                f"Failed to list entries for scope={scope!r}: {exc}"
            ) from exc

    def clear(self, scope: str) -> int:
        """Delete every entry in *scope*."""
        with self._write_lock:
            try:
                cur = self._conn.execute(
                    "DELETE FROM memory_entries WHERE scope = ?",
                    (scope,),
                )
                self._conn.commit()
                logger.debug(
                    "Cleared %d entries in scope=%r", cur.rowcount, scope
                )
                return cur.rowcount
            except sqlite3.Error as exc:
                raise MemoryBackendError(
                    f"Failed to clear scope={scope!r}: {exc}"
                ) from exc

    def clear_all(self) -> int:
        """Delete every entry across all scopes."""
        with self._write_lock:
            try:
                cur = self._conn.execute("DELETE FROM memory_entries")
                self._conn.commit()
                logger.debug("Cleared all %d entries.", cur.rowcount)
                return cur.rowcount
            except sqlite3.Error as exc:
                raise MemoryBackendError(
                    f"Failed to clear all entries: {exc}"
                ) from exc

    # -- extras ---------------------------------------------------------------

    def vacuum(self) -> None:
        """Run an explicit expired-entry sweep and SQLite ``VACUUM``.

        Call this periodically to reclaim disk space and rebuild the FTS
        index.
        """
        with self._write_lock:
            self._sweep_expired()
            try:
                self._conn.execute("VACUUM")
                logger.debug("SQLite VACUUM completed.")
            except sqlite3.Error as exc:
                raise MemoryBackendError(
                    f"VACUUM failed: {exc}"
                ) from exc

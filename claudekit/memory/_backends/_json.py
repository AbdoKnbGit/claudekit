"""JSON-file backend for the memory subsystem.

Stores all entries in a single JSON file.  Thread safety is achieved via
platform-specific file locking (``msvcrt`` on Windows, ``fcntl`` on Unix).
Writes are atomic: data is first written to a temporary file in the same
directory, then renamed over the target path.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from claudekit.errors import MemoryBackendError
from claudekit.memory._backends._base import AbstractBackend
from claudekit.memory._entry import MemoryEntry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Platform-specific file-lock helpers
# ---------------------------------------------------------------------------

_IS_WINDOWS = sys.platform == "win32"

if _IS_WINDOWS:
    import msvcrt  # noqa: WPS433 — conditional import

    def _lock(fh: Any) -> None:  # noqa: ANN401
        """Acquire an exclusive lock on *fh* (Windows)."""
        msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK, 1)

    def _unlock(fh: Any) -> None:  # noqa: ANN401
        """Release the lock on *fh* (Windows)."""
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)

else:
    import fcntl  # noqa: WPS433

    def _lock(fh: Any) -> None:  # noqa: ANN401
        """Acquire an exclusive lock on *fh* (Unix)."""
        fcntl.flock(fh, fcntl.LOCK_EX)

    def _unlock(fh: Any) -> None:  # noqa: ANN401
        """Release the lock on *fh* (Unix)."""
        fcntl.flock(fh, fcntl.LOCK_UN)


class JSONFileBackend(AbstractBackend):
    """Persist memory entries in a single JSON file on disk.

    Parameters
    ----------
    path:
        Location of the JSON file.  Parent directories are created
        automatically if they do not exist.  Defaults to
        ``~/.claudekit/memory.json``.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        if path is None:
            path = Path.home() / ".claudekit" / "memory.json"
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        logger.debug("JSONFileBackend initialised at %s", self._path)

    # -- internal helpers -----------------------------------------------------

    def _read_all(self) -> list[dict[str, Any]]:
        """Read and return every raw entry dict from disk."""
        if not self._path.exists():
            return []
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                _lock(fh)
                try:
                    content = fh.read()
                finally:
                    _unlock(fh)
            if not content.strip():
                return []
            data = json.loads(content)
            if not isinstance(data, list):
                logger.warning("Corrupt memory file (not a list); resetting.")
                return []
            return data  # type: ignore[no-any-return]
        except (json.JSONDecodeError, OSError) as exc:
            raise MemoryBackendError(
                f"Failed to read memory file {self._path}: {exc}"
            ) from exc

    def _write_all(self, entries: list[dict[str, Any]]) -> None:
        """Atomically write *entries* to disk.

        Writes to a temporary file first, then renames it over the target.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd, tmp_path = tempfile.mkstemp(
                dir=str(self._path.parent),
                suffix=".tmp",
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(entries, fh, indent=2, ensure_ascii=False)
                # Atomic rename (on Windows os.replace is atomic per-file).
                os.replace(tmp_path, str(self._path))
            except (json.JSONDecodeError, OSError, KeyError, TypeError):
                # Clean up temp file on failure.
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except OSError as exc:
            raise MemoryBackendError(
                f"Failed to write memory file {self._path}: {exc}"
            ) from exc

    def _clean_expired(
        self, entries: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Remove entries whose ``expires_at`` is in the past."""
        now = datetime.now(timezone.utc)
        cleaned: list[dict[str, Any]] = []
        removed = 0
        for entry in entries:
            expires = entry.get("expires_at")
            if expires is not None:
                if datetime.fromisoformat(expires) <= now:
                    removed += 1
                    continue
            cleaned.append(entry)
        if removed:
            logger.debug("Cleaned %d expired entries.", removed)
        return cleaned

    @staticmethod
    def _matches_scope(
        entry: dict[str, Any], scope: str | None
    ) -> bool:
        return entry.get("scope") == scope

    # -- AbstractBackend implementation ---------------------------------------

    def save(self, entry: MemoryEntry) -> None:
        """Persist *entry*, cleaning expired entries first."""
        with self._lock:
            entries = self._read_all()
            entries = self._clean_expired(entries)

            # Upsert: replace existing entry with same (key, scope).
            new_entries: list[dict[str, Any]] = []
            replaced = False
            for existing in entries:
                if (
                    existing["key"] == entry.key
                    and existing.get("scope") == entry.scope
                ):
                    new_entries.append(entry.to_dict())
                    replaced = True
                else:
                    new_entries.append(existing)

            if not replaced:
                new_entries.append(entry.to_dict())

            self._write_all(new_entries)
            logger.debug("Saved entry key=%r scope=%r", entry.key, entry.scope)

    def get(self, key: str, scope: str | None = None) -> MemoryEntry | None:
        """Return the entry for *(key, scope)* or ``None``."""
        with self._lock:
            for raw in self._read_all():
                if raw["key"] == key and raw.get("scope") == scope:
                    entry = MemoryEntry.from_dict(raw)
                    # Lazy expiry check.
                    if (
                        entry.expires_at is not None
                        and entry.expires_at <= datetime.now(timezone.utc)
                    ):
                        return None
                    return entry
        return None

    def search(
        self,
        query: str,
        scope: str | None = None,
        limit: int = 10,
    ) -> list[MemoryEntry]:
        """Substring search across keys and values."""
        query_lower = query.lower()
        results: list[MemoryEntry] = []
        now = datetime.now(timezone.utc)
        with self._lock:
            for raw in self._read_all():
                if not self._matches_scope(raw, scope):
                    continue
                entry = MemoryEntry.from_dict(raw)
                if entry.expires_at is not None and entry.expires_at <= now:
                    continue
                if (
                    query_lower in entry.key.lower()
                    or query_lower in entry.value.lower()
                ):
                    results.append(entry)
                    if len(results) >= limit:
                        break
        return results

    def delete(self, key: str, scope: str | None = None) -> bool:
        """Delete the entry for *(key, scope)*."""
        with self._lock:
            entries = self._read_all()
            new_entries = [
                e
                for e in entries
                if not (e["key"] == key and e.get("scope") == scope)
            ]
            if len(new_entries) == len(entries):
                return False
            self._write_all(new_entries)
            logger.debug("Deleted entry key=%r scope=%r", key, scope)
            return True

    def list_entries(self, scope: str | None = None) -> list[MemoryEntry]:
        """Return all non-expired entries in *scope*, sorted by updated_at."""
        now = datetime.now(timezone.utc)
        results: list[MemoryEntry] = []
        with self._lock:
            for raw in self._read_all():
                if not self._matches_scope(raw, scope):
                    continue
                entry = MemoryEntry.from_dict(raw)
                if entry.expires_at is not None and entry.expires_at <= now:
                    continue
                results.append(entry)
        results.sort(key=lambda e: e.updated_at)
        return results

    def clear(self, scope: str) -> int:
        """Delete every entry in *scope*."""
        with self._lock:
            entries = self._read_all()
            new_entries = [e for e in entries if e.get("scope") != scope]
            removed = len(entries) - len(new_entries)
            if removed:
                self._write_all(new_entries)
                logger.debug(
                    "Cleared %d entries in scope=%r", removed, scope
                )
            return removed

    def clear_all(self) -> int:
        """Delete every entry across all scopes."""
        with self._lock:
            entries = self._read_all()
            count = len(entries)
            if count:
                self._write_all([])
                logger.debug("Cleared all %d entries.", count)
            return count

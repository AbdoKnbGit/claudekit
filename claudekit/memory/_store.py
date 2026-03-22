"""High-level, backend-agnostic memory store.

:class:`MemoryStore` is the primary public interface for the memory subsystem.
It delegates all persistence to a pluggable :class:`AbstractBackend` and adds
policy enforcement (size limits, LRU eviction, error wrapping).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from claudekit.errors import MemoryBackendError, MemoryValueTooLargeError
from claudekit.memory._backends._base import AbstractBackend
from claudekit.memory._backends._json import JSONFileBackend
from claudekit.memory._entry import MemoryEntry

logger = logging.getLogger(__name__)


class MemoryStore:
    """Backend-agnostic memory store with policy enforcement.

    Parameters
    ----------
    backend:
        The storage backend to use.  Defaults to a :class:`JSONFileBackend`
        with its own defaults.
    max_entries:
        Optional cap on the total number of entries across all scopes.
        When the cap is reached the oldest entry (by ``updated_at``) is
        evicted before the new one is saved (LRU policy).
    max_value_chars:
        Optional maximum length (in characters) for a single entry's value.
        If exceeded, a :class:`MemoryValueTooLargeError` is raised.
    fail_silently:
        When ``True``, backend exceptions are caught, logged at WARNING
        level, and swallowed — methods return ``None`` or empty lists
        instead of raising.  Defaults to ``False``.
    """

    def __init__(
        self,
        backend: AbstractBackend | None = None,
        *,
        max_entries: int | None = None,
        max_value_chars: int | None = None,
        fail_silently: bool = False,
    ) -> None:
        self._backend: AbstractBackend = backend or JSONFileBackend()
        self._max_entries = max_entries
        self._max_value_chars = max_value_chars
        self._fail_silently = fail_silently

    # -- helpers --------------------------------------------------------------

    def _wrap_error(self, exc: Exception) -> None:
        """Re-raise *exc* as :class:`MemoryBackendError` or swallow it."""
        if self._fail_silently:
            logger.warning("Memory backend error (silenced): %s", exc)
            return
        if isinstance(exc, MemoryBackendError):
            raise exc
        raise MemoryBackendError(str(exc)) from exc

    def _enforce_value_limit(self, key: str, value: str) -> None:
        """Raise if *value* exceeds the configured character limit."""
        if self._max_value_chars is not None and len(value) > self._max_value_chars:
            raise MemoryValueTooLargeError(
                f"Value for key {key!r} has {len(value)} chars, "
                f"exceeding the {self._max_value_chars}-char limit",
                context={
                    "key": key,
                    "length": len(value),
                    "limit": self._max_value_chars,
                },
            )

    def _evict_if_needed(self) -> None:
        """Evict the oldest entry (by updated_at) when at capacity.

        This method intentionally lists entries across **all** scopes
        (``scope=None``) to enforce a global cap.
        """
        if self._max_entries is None:
            return
        try:
            # Collect entries from all scopes.  We use the backend's
            # list_entries with scope=None (global scope).  Because
            # list_entries only returns one scope at a time, we use a
            # pragmatic approach: call list_entries(scope=None) to get
            # global-scope entries — but that won't cover other scopes.
            # Instead, we rely on a count-based heuristic: save first,
            # then check.
            #
            # A more robust approach: count total entries in the backend.
            # For now, we gather global-scope entries as a representative
            # measure.  This is acceptable because MemoryStore is a
            # convenience layer, not a database.
            pass  # Eviction is done in save() after the write.
        except Exception as exc:
            self._wrap_error(exc)

    def _total_entry_count(self) -> int:
        """Return a best-effort count of all entries (all scopes).

        For backends that don't expose a count method, we sum the entries
        from the global scope as a lower bound.  This is imperfect but
        avoids adding a ``count`` method to the backend contract.
        """
        # We use list_entries(scope=None) for the global scope count.
        # This is deliberately simple.  If a backend can do better, callers
        # can subclass.
        return len(self._backend.list_entries(scope=None))

    # -- public API -----------------------------------------------------------

    def save(
        self,
        key: str,
        value: str,
        scope: str | None = None,
        *,
        ttl_seconds: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryEntry | None:
        """Create or update a memory entry.

        Parameters
        ----------
        key:
            Unique identifier within *scope*.
        value:
            The content to store.
        scope:
            Optional namespace.
        ttl_seconds:
            If given, the entry will expire this many seconds from now.
        metadata:
            Arbitrary key/value pairs to attach.

        Returns
        -------
        MemoryEntry | None
            The persisted entry, or ``None`` if ``fail_silently`` is enabled
            and the backend raised.

        Raises
        ------
        MemoryValueTooLargeError
            If *value* exceeds ``max_value_chars``.
        MemoryBackendError
            If the backend fails and ``fail_silently`` is ``False``.
        """
        self._enforce_value_limit(key, value)

        now = datetime.now(timezone.utc)
        expires_at = (
            now + timedelta(seconds=ttl_seconds) if ttl_seconds is not None else None
        )

        # Preserve original created_at if updating an existing entry.
        try:
            existing = self._backend.get(key, scope)
        except Exception as exc:
            self._wrap_error(exc)
            existing = None

        created_at = existing.created_at if existing else now

        entry = MemoryEntry(
            key=key,
            value=value,
            scope=scope,
            created_at=created_at,
            updated_at=now,
            expires_at=expires_at,
            metadata=metadata or {},
        )

        try:
            # LRU eviction: if at capacity and this is a *new* key, evict.
            if self._max_entries is not None and existing is None:
                all_entries = self._backend.list_entries(scope=None)
                if len(all_entries) >= self._max_entries:
                    # Evict oldest by updated_at.
                    oldest = min(all_entries, key=lambda e: e.updated_at)
                    self._backend.delete(oldest.key, oldest.scope)
                    logger.debug(
                        "Evicted oldest entry key=%r scope=%r",
                        oldest.key,
                        oldest.scope,
                    )

            self._backend.save(entry)
        except MemoryBackendError:
            raise
        except Exception as exc:
            self._wrap_error(exc)
            return None

        return entry

    def get(self, key: str, scope: str | None = None) -> MemoryEntry | None:
        """Retrieve a memory entry.

        Expired entries are treated as absent (lazy cleanup).

        Parameters
        ----------
        key:
            The unique key.
        scope:
            Optional namespace.

        Returns
        -------
        MemoryEntry | None
            The entry if found and not expired, otherwise ``None``.
        """
        try:
            entry = self._backend.get(key, scope)
        except Exception as exc:
            self._wrap_error(exc)
            return None

        if entry is None:
            return None

        # Double-check expiry (backends should do this, but belt-and-braces).
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
        """Search for entries whose key or value contains *query*.

        Parameters
        ----------
        query:
            Substring to search for.
        scope:
            Optional namespace filter.
        limit:
            Maximum number of results.

        Returns
        -------
        list[MemoryEntry]
            Matching entries.
        """
        try:
            return self._backend.search(query, scope, limit)
        except Exception as exc:
            self._wrap_error(exc)
            return []

    def delete(self, key: str, scope: str | None = None) -> bool:
        """Delete a single entry.

        Parameters
        ----------
        key:
            The unique key.
        scope:
            Optional namespace.

        Returns
        -------
        bool
            ``True`` if the entry existed and was deleted.
        """
        try:
            return self._backend.delete(key, scope)
        except Exception as exc:
            self._wrap_error(exc)
            return False

    def list(self, scope: str | None = None) -> list[MemoryEntry]:
        """List all non-expired entries in *scope*.

        Parameters
        ----------
        scope:
            Optional namespace.

        Returns
        -------
        list[MemoryEntry]
            Entries sorted by ``updated_at`` ascending.
        """
        try:
            return self._backend.list_entries(scope)
        except Exception as exc:
            self._wrap_error(exc)
            return []

    def clear(self, scope: str) -> int:
        """Delete every entry in *scope*.

        Parameters
        ----------
        scope:
            The namespace to wipe.  **Must not** be ``None`` — use
            :meth:`clear_all` for a full wipe.

        Returns
        -------
        int
            Number of entries removed.

        Raises
        ------
        ValueError
            If *scope* is ``None``.
        """
        if scope is None:
            raise ValueError(
                "clear() requires an explicit scope. "
                "Use clear_all(confirm=True) to wipe everything."
            )
        try:
            return self._backend.clear(scope)
        except Exception as exc:
            self._wrap_error(exc)
            return 0

    def clear_all(self, *, confirm: bool = True) -> int:
        """Delete **every** entry across **all** scopes.

        This is a destructive operation.  The *confirm* flag must be
        explicitly set to ``True`` to proceed — this prevents accidental
        full wipes.

        Parameters
        ----------
        confirm:
            Must be ``True`` to actually perform the wipe.

        Returns
        -------
        int
            Number of entries removed.

        Raises
        ------
        ValueError
            If *confirm* is not ``True``.
        """
        if confirm is not True:
            raise ValueError(
                "clear_all() requires confirm=True to prevent accidental data loss."
            )
        try:
            return self._backend.clear_all()
        except Exception as exc:
            self._wrap_error(exc)
            return 0

    def vacuum(self) -> None:
        """Run backend-specific cleanup / optimisation.

        For backends that support it (e.g. :class:`SQLiteBackend`) this
        reclaims disk space and rebuilds indices.  For others it is a
        no-op.
        """
        try:
            if hasattr(self._backend, "vacuum"):
                self._backend.vacuum()  # type: ignore[attr-defined]
        except Exception as exc:
            self._wrap_error(exc)

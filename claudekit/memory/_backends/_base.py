"""Abstract base class for all memory backends.

Every concrete backend must subclass :class:`AbstractBackend` and implement
every abstract method listed here.  The :class:`~claudekit.memory.MemoryStore`
facade delegates all persistence work to the backend, so correct
implementation of this contract is critical.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from claudekit.memory._entry import MemoryEntry

logger = logging.getLogger(__name__)


class AbstractBackend(ABC):
    """Contract that every memory-storage backend must fulfil.

    Implementations are responsible for:

    * Persisting :class:`MemoryEntry` objects durably across process restarts.
    * Honouring the *scope* parameter so that different namespaces are
      logically isolated.
    * Being thread-safe — the store may be accessed from multiple threads
      concurrently.
    """

    # -- write / read ---------------------------------------------------------

    @abstractmethod
    def save(self, entry: MemoryEntry) -> None:
        """Persist *entry*, creating or updating as needed.

        If an entry with the same ``(key, scope)`` pair already exists, it
        must be overwritten.

        Parameters
        ----------
        entry:
            The memory entry to persist.

        Raises
        ------
        claudekit.errors.MemoryBackendError
            If the underlying storage operation fails.
        """

    @abstractmethod
    def get(self, key: str, scope: str | None = None) -> MemoryEntry | None:
        """Retrieve a single entry by key and scope.

        Parameters
        ----------
        key:
            The unique key of the entry.
        scope:
            Optional namespace.  ``None`` means the global scope.

        Returns
        -------
        MemoryEntry | None
            The entry if found, otherwise ``None``.

        Raises
        ------
        claudekit.errors.MemoryBackendError
            If the underlying storage operation fails.
        """

    @abstractmethod
    def search(
        self,
        query: str,
        scope: str | None = None,
        limit: int = 10,
    ) -> list[MemoryEntry]:
        """Search entries whose key or value contains *query*.

        Parameters
        ----------
        query:
            Substring to match against entry keys and values.
        scope:
            Optional namespace filter.  ``None`` means the global scope.
        limit:
            Maximum number of results to return.

        Returns
        -------
        list[MemoryEntry]
            Matching entries, ordered by relevance or recency (backend
            decides).

        Raises
        ------
        claudekit.errors.MemoryBackendError
            If the underlying storage operation fails.
        """

    @abstractmethod
    def delete(self, key: str, scope: str | None = None) -> bool:
        """Remove a single entry.

        Parameters
        ----------
        key:
            The unique key of the entry to remove.
        scope:
            Optional namespace.

        Returns
        -------
        bool
            ``True`` if an entry was actually deleted, ``False`` if the key
            did not exist.

        Raises
        ------
        claudekit.errors.MemoryBackendError
            If the underlying storage operation fails.
        """

    @abstractmethod
    def list_entries(self, scope: str | None = None) -> list[MemoryEntry]:
        """List every entry in *scope*.

        Parameters
        ----------
        scope:
            Optional namespace.  ``None`` means the global scope.

        Returns
        -------
        list[MemoryEntry]
            All entries in the requested scope, ordered by ``updated_at``
            ascending.

        Raises
        ------
        claudekit.errors.MemoryBackendError
            If the underlying storage operation fails.
        """

    @abstractmethod
    def clear(self, scope: str) -> int:
        """Delete every entry in *scope*.

        Parameters
        ----------
        scope:
            The namespace to wipe.  Must not be ``None``.

        Returns
        -------
        int
            Number of entries removed.

        Raises
        ------
        claudekit.errors.MemoryBackendError
            If the underlying storage operation fails.
        """

    @abstractmethod
    def clear_all(self) -> int:
        """Delete **every** entry across **all** scopes.

        Returns
        -------
        int
            Total number of entries removed.

        Raises
        ------
        claudekit.errors.MemoryBackendError
            If the underlying storage operation fails.
        """

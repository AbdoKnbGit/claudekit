"""Memory entry data model.

A :class:`MemoryEntry` is the atomic unit of cross-session memory.  It can be
serialised to / from plain dicts for storage in any backend.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    """A single memory record.

    Parameters
    ----------
    key:
        Unique identifier within a scope.
    value:
        The stored content (free-form text).
    scope:
        Optional namespace for logical grouping (e.g. ``"project-x"``).
    created_at:
        Timestamp when the entry was first persisted.
    updated_at:
        Timestamp of the most recent write.
    expires_at:
        Optional expiry; ``None`` means the entry never expires.
    metadata:
        Arbitrary key/value pairs attached to the entry.
    """

    key: str
    value: str
    scope: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    # -- serialisation --------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialise the entry to a plain dictionary.

        Datetime values are stored as ISO-8601 strings in UTC.

        Returns
        -------
        dict[str, Any]
            A JSON-compatible dictionary representation.
        """
        return {
            "key": self.key,
            "value": self.value,
            "scope": self.scope,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryEntry:
        """Reconstruct a :class:`MemoryEntry` from a plain dictionary.

        Parameters
        ----------
        data:
            Dictionary as produced by :meth:`to_dict`.

        Returns
        -------
        MemoryEntry
            The reconstituted entry.
        """
        return cls(
            key=data["key"],
            value=data["value"],
            scope=data.get("scope"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            expires_at=(
                datetime.fromisoformat(data["expires_at"])
                if data.get("expires_at")
                else None
            ),
            metadata=data.get("metadata", {}),
        )

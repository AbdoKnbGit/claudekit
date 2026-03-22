"""Batch result types.

:class:`BatchResult` holds the outcome of a completed batch, alongside
:class:`BatchStats` which summarises success / failure counts and cost.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List

logger = logging.getLogger(__name__)


@dataclass
class BatchStats:
    """Aggregate statistics for a completed batch.

    Attributes
    ----------
    succeeded:
        Number of requests that completed successfully.
    failed:
        Number of requests that returned an error.
    expired:
        Number of requests that expired before processing.
    cancelled:
        Number of requests that were cancelled.
    total_cost:
        Estimated total cost in USD (at the 50% batch discount rate).
    """

    succeeded: int = 0
    failed: int = 0
    expired: int = 0
    cancelled: int = 0
    total_cost: float = 0.0

    @property
    def total(self) -> int:
        """Total number of entries across all outcome categories."""
        return self.succeeded + self.failed + self.expired + self.cancelled

    @property
    def success_rate(self) -> float:
        """Fraction of entries that succeeded (0.0 -- 1.0).

        Returns 0.0 if there are no entries.
        """
        total = self.total
        if total == 0:
            return 0.0
        return self.succeeded / total

    def summary(self) -> str:
        """Human-readable one-line summary of batch outcomes.

        Returns:
            Formatted string.
        """
        return (
            f"Batch: {self.succeeded} succeeded, {self.failed} failed, "
            f"{self.expired} expired, {self.cancelled} cancelled "
            f"(${self.total_cost:.6f})"
        )


class BatchResult:
    """Container for completed batch entries and their aggregate statistics.

    Parameters
    ----------
    entries:
        The list of result entry dicts returned by the API.
    stats:
        Pre-computed :class:`BatchStats` for the batch.

    Example
    -------
    ::

        result = await batch_manager.wait(batch_id)
        for entry in result:
            print(entry["custom_id"], entry["result"]["type"])
        print(result.stats.summary())
    """

    def __init__(
        self,
        entries: List[Dict[str, Any]],
        stats: BatchStats,
    ) -> None:
        self.entries: List[Dict[str, Any]] = entries
        self.stats: BatchStats = stats

    def __iter__(self) -> Iterator[Dict[str, Any]]:
        """Iterate over result entries."""
        return iter(self.entries)

    def __len__(self) -> int:
        """Return the number of result entries."""
        return len(self.entries)

    def succeeded(self) -> List[Dict[str, Any]]:
        """Return only the entries that succeeded.

        Returns:
            List of entries whose ``result.type`` is ``"succeeded"``.
        """
        return [
            e for e in self.entries
            if e.get("result", {}).get("type") == "succeeded"
        ]

    def failed(self) -> List[Dict[str, Any]]:
        """Return only the entries that failed.

        Returns:
            List of entries whose ``result.type`` is not ``"succeeded"``.
        """
        return [
            e for e in self.entries
            if e.get("result", {}).get("type") != "succeeded"
        ]

    def __repr__(self) -> str:
        return (
            f"BatchResult(entries={len(self.entries)}, "
            f"succeeded={self.stats.succeeded}, failed={self.stats.failed})"
        )


__all__ = ["BatchResult", "BatchStats"]

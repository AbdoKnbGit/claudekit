"""claudekit.batches -- Batch request building, submission, and result handling.

This module provides:

- :class:`BatchBuilder` -- fluent API for constructing batch requests.
- :class:`BatchManager` -- submission, polling, cancellation, and persistence.
- :class:`BatchResult` -- container for completed batch entries.
- :class:`BatchStats` -- aggregate statistics for batch outcomes.
"""

from __future__ import annotations

from claudekit.batches._builder import BatchBuilder
from claudekit.batches._manager import BatchManager
from claudekit.batches._result import BatchResult, BatchStats

__all__ = [
    "BatchBuilder",
    "BatchManager",
    "BatchResult",
    "BatchStats",
]

"""Pluggable storage backends for the memory subsystem.

Public API
----------
.. autoclass:: AbstractBackend
.. autoclass:: JSONFileBackend
.. autoclass:: SQLiteBackend
"""

from __future__ import annotations

from claudekit.memory._backends._base import AbstractBackend
from claudekit.memory._backends._json import JSONFileBackend
from claudekit.memory._backends._sqlite import SQLiteBackend

__all__ = [
    "AbstractBackend",
    "JSONFileBackend",
    "SQLiteBackend",
]

"""Cross-session memory with pluggable backends.

Quick start::

    from claudekit.memory import MemoryStore

    store = MemoryStore()                     # JSON file by default
    store.save("user-lang", "Python")
    print(store.get("user-lang").value)       # "Python"

    # SQLite backend for full-text search
    from claudekit.memory import SQLiteBackend
    store = MemoryStore(backend=SQLiteBackend())

Public API
----------
.. autoclass:: MemoryStore
.. autoclass:: MemoryEntry
.. autoclass:: AbstractBackend
.. autoclass:: JSONFileBackend
.. autoclass:: SQLiteBackend
.. autofunction:: context_with_memory
"""

from __future__ import annotations

from claudekit.memory._backends._base import AbstractBackend
from claudekit.memory._backends._json import JSONFileBackend
from claudekit.memory._backends._sqlite import SQLiteBackend
from claudekit.memory._entry import MemoryEntry
from claudekit.memory._injection import context_with_memory
from claudekit.memory._store import MemoryStore

__all__ = [
    "AbstractBackend",
    "JSONFileBackend",
    "MemoryEntry",
    "MemoryStore",
    "SQLiteBackend",
    "context_with_memory",
]

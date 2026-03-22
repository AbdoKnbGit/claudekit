---
title: Memory
description: MemoryStore and backend drivers for cross-session key-value persistence with TTL, search, and optional SQLite or JSON file storage.
module: claudekit.memory
classes: [MemoryStore, MemoryEntry, SQLiteBackend, JSONFileBackend, AbstractBackend]
exports: [MemoryStore, MemoryEntry, SQLiteBackend, JSONFileBackend, context_with_memory]
---

# Memory

`claudekit.memory` provides cross-session, scoped key-value storage with TTL, full-text search, and pluggable backends.

## MemoryStore

The primary interface. Delegates persistence to a backend, adds policy enforcement (size limits, LRU eviction, error wrapping).

```python
from claudekit.memory import MemoryStore
from claudekit.memory import SQLiteBackend

mem = MemoryStore(
    backend=SQLiteBackend("~/.myapp/memory.db"),  # default: JSONFileBackend
    max_entries=1000,           # optional global cap (LRU eviction)
    max_value_chars=50_000,     # optional per-entry char limit
    fail_silently=False,        # True: catch backend errors, return None
)
```

### Constructor

```python
MemoryStore(
    backend: AbstractBackend | None = None,  # default: JSONFileBackend()
    *,
    max_entries: int | None = None,
    max_value_chars: int | None = None,
    fail_silently: bool = False,
)
```

### save

```python
entry = mem.save(
    key="user-prefs",
    value="Prefers concise answers",
    scope="user-42",          # optional namespace
    ttl_seconds=3600,         # optional TTL
    metadata={"source": "onboarding"},  # optional arbitrary dict
)
# Returns MemoryEntry | None (None only if fail_silently=True and backend failed)
```

- Updates existing entry if key+scope already exists (preserves `created_at`).
- Evicts the oldest entry (by `updated_at`) if `max_entries` is reached.

### get

```python
entry = mem.get("user-prefs", scope="user-42")
# Returns MemoryEntry | None
# Expired entries are treated as absent (lazy TTL enforcement)
if entry:
    print(entry.value)
```

### search

```python
results = mem.search(
    query="concise",
    scope="user-42",   # optional
    limit=10,          # default 10
)
# Returns list[MemoryEntry]
# SQLiteBackend: FTS5 full-text search on key+value
# JSONFileBackend: substring match
```

### delete / list / clear

```python
mem.delete("user-prefs", scope="user-42")    # bool — True if existed
entries = mem.list(scope="user-42")           # list[MemoryEntry], sorted by updated_at
count = mem.clear(scope="user-42")            # int — entries removed (scope required)
count = mem.clear_all(confirm=True)           # wipe every scope (confirm=True required)
mem.vacuum()                                  # SQLiteBackend: VACUUM + REINDEX
```

---

## MemoryEntry

Atomic unit of storage.

```python
from claudekit.memory import MemoryEntry

entry = mem.get("key", scope="scope")

entry.key          # str
entry.value        # str
entry.scope        # str | None
entry.created_at   # datetime (UTC)
entry.updated_at   # datetime (UTC)
entry.expires_at   # datetime | None — None means never expires
entry.metadata     # dict[str, Any]

# Serialisation
d = entry.to_dict()        # JSON-compatible dict
e = MemoryEntry.from_dict(d)
```

---

## Backends

### SQLiteBackend

Recommended for production. Uses WAL mode, FTS5 virtual table for full-text search, and auto-cleanup of expired entries every 100 writes.

```python
from claudekit.memory import SQLiteBackend

backend = SQLiteBackend(path="~/.myapp/memory.db")
# Defaults to ~/.claudekit/memory.db
```

- Thread-safe (`check_same_thread=False` + write lock).
- FTS5 full-text search on key + value.
- Persists across process restarts.

### JSONFileBackend

Simple, no-dependency JSON file storage. Good for development and testing.

```python
from claudekit.memory import JSONFileBackend

backend = JSONFileBackend(path="~/.myapp/memory.json")
# Defaults to ~/.claudekit/memory.json
```

- Not optimized for large datasets.
- Search is a substring match (no FTS).
- Rewrites the full file on every write.

### AbstractBackend

Base class for custom backends. Implement all abstract methods:

```python
from claudekit.memory._backends._base import AbstractBackend
from claudekit.memory._entry import MemoryEntry

class RedisBackend(AbstractBackend):
    def save(self, entry: MemoryEntry) -> None: ...
    def get(self, key: str, scope: str | None) -> MemoryEntry | None: ...
    def delete(self, key: str, scope: str | None) -> bool: ...
    def list_entries(self, scope: str | None) -> list[MemoryEntry]: ...
    def search(self, query: str, scope: str | None, limit: int) -> list[MemoryEntry]: ...
    def clear(self, scope: str) -> int: ...
    def clear_all(self) -> int: ...
```

---

## context_with_memory

Enriches a message list with relevant memories before sending to the API.

```python
from claudekit.memory import context_with_memory

enriched = context_with_memory(
    messages=[{"role": "user", "content": "Tell me about Python."}],
    memory_store=mem,
    scope="project",   # optional scope filter
    limit=5,           # max entries to inject (default 5)
)
# Prepends a system message with matching entries when found.
# Returns messages unchanged if no matches found.
```

**How it works:** extracts the most recent user message as the search query, calls `mem.search()`, and prepends the matching entries as a system message at the start of the conversation.

---

## Attach to TrackedClient

```python
from claudekit import TrackedClient
from claudekit.memory import MemoryStore, SQLiteBackend

mem = MemoryStore(backend=SQLiteBackend("~/.myapp/mem.db"))
client = TrackedClient(memory=mem)
# client.memory is accessible but memory injection is manual via context_with_memory
```

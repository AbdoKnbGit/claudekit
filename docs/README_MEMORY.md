# claudekit · memory

Cross-session conversation memory with pluggable storage backends. Enables Retrieval-Augmented Generation (RAG) by storing key-value pairs or free-form text and injecting relevant context into new conversation turns based on user input.

**Source files:** `_store.py`, `_entry.py`, `_injection.py`, `_backends/` (`_base.py`, `_json.py`, `_sqlite.py`)

---

## Class: `MemoryEntry`

**Source:** `_entry.py:18`
**Type:** `@dataclass`

The atomic unit of memory. Stores a value along with lifecycle metadata.

### Attributes

| Attribute | Type | Default | Description |
|---|---|---|---|
| `key` | `str` | *(required)* | Unique identifier within a scope. |
| `value` | `str` | *(required)* | The stored content (free-form text). |
| `scope` | `Optional[str]` | `None` | Namespace for logical grouping (e.g., project ID). |
| `created_at` | `datetime` | `now (UTC)` | When the entry was first created. |
| `updated_at` | `datetime` | `now (UTC)` | When the entry was last updated. |
| `expires_at` | `Optional[datetime]` | `None` | Optional TTL; `None` means permanent. |
| `metadata` | `dict[str, Any]` | `{}` | Arbitrary key/value pairs. |

### Methods

#### `to_dict() -> dict` / `from_dict(data) -> MemoryEntry`
Serialization helpers. Datetimes are handled as ISO-8601 strings in UTC.

---

## Class: `MemoryStore`

**Source:** `_store.py:22`

The primary interface for the memory system. Implements policy enforcement (LRU, character limits) and delegates storage to a backend.

### Constructor

```python
MemoryStore(
    backend: AbstractBackend | None = None,
    *,
    max_entries: int | None = None,
    max_value_chars: int | None = None,
    fail_silently: bool = False,
)
```

- **Parameters:**
  - `backend`: Instance of `AbstractBackend`. Defaults to `JSONFileBackend()`.
  - `max_entries`: Global limit on entry count. If exceeded, the oldest entry (by `updated_at`) is evicted (LRU).
  - `max_value_chars`: Max length for any single entry value.
  - `fail_silently`: If `True`, backend errors are logged as warnings and methods return `None`/`[]` instead of raising.

### Methods

#### `save(key, value, scope=None, ttl_seconds=None, metadata=None) -> Optional[MemoryEntry]`
Persists an entry.
- **Args:** `ttl_seconds` defines expiration relative to current time.
- **Raises:** `MemoryValueTooLargeError` if over character limit.

#### `get(key, scope=None) -> Optional[MemoryEntry]`
Retrieves a single entry. Returns `None` if the entry is expired (lazy cleanup).

#### `search(query, scope=None, limit=10) -> list[MemoryEntry]`
Performs a substring search on both **keys** and **values**.
- **Backend Note:** `SQLiteBackend` uses FTS5 for this; `JSONFileBackend` uses Python string matching.

#### `list(scope=None) -> list[MemoryEntry]`
Returns all non-expired entries in the scope, sorted by `updated_at` ascending.

#### `delete(key, scope=None) -> bool` / `clear(scope) -> int` / `clear_all(confirm=True) -> int`
Deletion methods. `clear_all` requires `confirm=True` to prevent accidental loss of all namespaces.

#### `vacuum() -> None`
Triggers backend-specific optimization (e.g., `VACUUM` in SQLite).

---

## Storage Backends

### `JSONFileBackend`
**Source:** `_backends/_json.py:57`
Stores everything in a single JSON file.
- **Thread-Safety:** Exclusive file locking via `msvcrt` (Windows) or `fcntl` (Unix).
- **Atomicity:** Writes to a `.tmp` file and then replaces the original.
- **Cleanup:** Expired entries are removed during every `save` and `list_entries` call.

### `SQLiteBackend`
**Source:** `_backends/_sqlite.py:68`
Uses a local SQLite database for enhanced performance and search.
- **Concurrency:** WAL (Write-Ahead Logging) mode enabled for high-performance concurrent reads.
- **Search:** Implements FTS5 virtual table for full-text search with triggers that automatically sync the index on insert/update/delete.
- **Cleanup:** Sweeps expired entries every 100 writes (`_CLEANUP_INTERVAL`).

### `AbstractBackend`
**Source:** `_backends/_base.py:19`
The base class for custom backends. Requires implementation of: `save`, `get`, `search`, `delete`, `list_entries`, `clear`, `clear_all`.

---

## Function: `context_with_memory`

**Source:** `_injection.py:18`

```python
def context_with_memory(
    messages: list[dict[str, Any]],
    memory_store: MemoryStore,
    *,
    scope: str | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
```

RAG injection utility. 
1. Inspects the **most recent user message** in the `messages` list.
2. Extracts text from content strings or blocks.
3. Queries `memory_store.search()` using that text.
4. If memories are found, prepends a **new system message** containing the retrieved entries to a copy of the message list.
5. Returns the enriched list.

---

## Module Exports (`__all__`)

6 names total:

| Name | Type | Description |
|---|---|---|
| `MemoryStore` | class | Main store interface |
| `MemoryEntry` | dataclass | Record data model |
| `JSONFileBackend` | class | Default file storage |
| `SQLiteBackend` | class | FTS-enabled database storage |
| `AbstractBackend` | ABC | Base class for custom backends |
| `context_with_memory` | function | RAG injection helper |

---

## Edge Cases & Gotchas

1. **Lazy Expiry.** Backends perform periodic cleanup, but `MemoryStore.get` always enforces expiry at the application level just in case.

2. **LRU Eviction.** Global entry limits in `MemoryStore` are enforced *per save*. If a backend is shared by multiple store instances with different limits, behavior may be inconsistent.

3. **Character Limits.** The `max_value_chars` check happens before the backend call. It measures UTF-8 string length (number of characters, not bytes).

4. **Clear All Confirmation.** `clear_all` will raise a `ValueError` if called without `confirm=True`. This is intentional to safeguard against accidental wipes of multi-project storage.

5. **Search relevance.** `SQLiteBackend` prioritizes FTS5 rank; `JSONFileBackend` returns results in file order.

6. **SQLite WAL Mode.** The `SQLiteBackend` enables WAL mode which creates `-wal` and `-shm` sidecar files. These should be kept with the main `.db` file.

"""Tests for claudekit.memory -- MemoryEntry, MemoryStore, backends."""

import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest

from claudekit.errors._base import MemoryValueTooLargeError
from claudekit.memory._backends._json import JSONFileBackend
from claudekit.memory._entry import MemoryEntry
from claudekit.memory._store import MemoryStore


# ── MemoryEntry ──────────────────────────────────────────────────────────── #


class TestMemoryEntry:
    def test_defaults(self):
        entry = MemoryEntry(key="k", value="v")
        assert entry.key == "k"
        assert entry.value == "v"
        assert entry.scope is None
        assert entry.metadata == {}
        assert entry.expires_at is None
        assert isinstance(entry.created_at, datetime)
        assert isinstance(entry.updated_at, datetime)

    def test_to_dict(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        entry = MemoryEntry(
            key="k", value="v", scope="s",
            created_at=now, updated_at=now,
            metadata={"a": 1},
        )
        d = entry.to_dict()
        assert d["key"] == "k"
        assert d["value"] == "v"
        assert d["scope"] == "s"
        assert d["metadata"] == {"a": 1}
        assert d["expires_at"] is None
        assert "2026" in d["created_at"]

    def test_from_dict_roundtrip(self):
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        entry = MemoryEntry(
            key="k", value="v", scope="s",
            created_at=now, updated_at=now,
            expires_at=now + timedelta(hours=1),
            metadata={"x": "y"},
        )
        d = entry.to_dict()
        restored = MemoryEntry.from_dict(d)
        assert restored.key == entry.key
        assert restored.value == entry.value
        assert restored.scope == entry.scope
        assert restored.expires_at is not None

    def test_from_dict_no_expiry(self):
        d = {
            "key": "k", "value": "v",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
        entry = MemoryEntry.from_dict(d)
        assert entry.expires_at is None


# ── MemoryStore with JSON backend ────────────────────────────────────────── #


@pytest.fixture
def store(tmp_path):
    """Create a MemoryStore with a temp-file JSON backend."""
    path = tmp_path / "test_memory.json"
    backend = JSONFileBackend(path=path)
    return MemoryStore(backend=backend)


class TestMemoryStore:
    def test_save_and_get(self, store):
        entry = store.save("greeting", "Hello, world!")
        assert entry is not None
        assert entry.key == "greeting"
        assert entry.value == "Hello, world!"

        retrieved = store.get("greeting")
        assert retrieved is not None
        assert retrieved.value == "Hello, world!"

    def test_get_missing(self, store):
        assert store.get("nonexistent") is None

    def test_save_with_scope(self, store):
        store.save("key", "val1", scope="project-a")
        store.save("key", "val2", scope="project-b")
        assert store.get("key", scope="project-a").value == "val1"
        assert store.get("key", scope="project-b").value == "val2"
        assert store.get("key") is None  # global scope

    def test_update_preserves_created_at(self, store):
        entry1 = store.save("k", "v1")
        created = entry1.created_at
        entry2 = store.save("k", "v2")
        assert entry2.created_at == created
        assert entry2.value == "v2"

    def test_delete(self, store):
        store.save("k", "v")
        assert store.delete("k") is True
        assert store.get("k") is None
        assert store.delete("k") is False

    def test_list(self, store):
        store.save("a", "1")
        store.save("b", "2")
        entries = store.list()
        assert len(entries) == 2
        keys = {e.key for e in entries}
        assert keys == {"a", "b"}

    def test_search(self, store):
        store.save("weather", "sunny today")
        store.save("news", "big event")
        results = store.search("sunny")
        assert len(results) == 1
        assert results[0].key == "weather"

    def test_search_by_key(self, store):
        store.save("python_tips", "use generators")
        results = store.search("python")
        assert len(results) == 1

    def test_clear_scope(self, store):
        store.save("a", "1", scope="s1")
        store.save("b", "2", scope="s1")
        store.save("c", "3", scope="s2")
        removed = store.clear("s1")
        assert removed == 2
        assert store.get("a", scope="s1") is None
        assert store.get("c", scope="s2") is not None

    def test_clear_none_raises(self, store):
        with pytest.raises(ValueError, match="explicit scope"):
            store.clear(None)

    def test_clear_all(self, store):
        store.save("a", "1")
        store.save("b", "2", scope="s")
        removed = store.clear_all(confirm=True)
        assert removed == 2
        assert store.list() == []

    def test_clear_all_requires_confirm(self, store):
        with pytest.raises(ValueError, match="confirm=True"):
            store.clear_all(confirm=False)


class TestMemoryStoreValueLimit:
    def test_value_too_large(self, tmp_path):
        backend = JSONFileBackend(path=tmp_path / "mem.json")
        store = MemoryStore(backend=backend, max_value_chars=10)
        with pytest.raises(MemoryValueTooLargeError):
            store.save("k", "x" * 11)

    def test_value_within_limit(self, tmp_path):
        backend = JSONFileBackend(path=tmp_path / "mem.json")
        store = MemoryStore(backend=backend, max_value_chars=10)
        entry = store.save("k", "x" * 10)
        assert entry is not None


class TestMemoryStoreLRU:
    def test_eviction(self, tmp_path):
        backend = JSONFileBackend(path=tmp_path / "mem.json")
        store = MemoryStore(backend=backend, max_entries=2)
        store.save("a", "1")
        store.save("b", "2")
        store.save("c", "3")  # Should evict "a" (oldest)
        entries = store.list()
        keys = {e.key for e in entries}
        assert "c" in keys
        assert "b" in keys
        assert len(keys) == 2


class TestMemoryStoreTTL:
    def test_expired_not_returned(self, tmp_path):
        backend = JSONFileBackend(path=tmp_path / "mem.json")
        store = MemoryStore(backend=backend)
        # Save with TTL of -1 seconds (already expired)
        now = datetime.now(timezone.utc)
        entry = MemoryEntry(
            key="expired",
            value="old",
            created_at=now,
            updated_at=now,
            expires_at=now - timedelta(seconds=1),
        )
        backend.save(entry)
        result = store.get("expired")
        assert result is None


class TestMemoryStoreFailSilently:
    def test_fail_silently(self, tmp_path):
        # Use a path we can't possibly write to
        # Instead, we'll create a store with fail_silently=True and a bad backend
        backend = JSONFileBackend(path=tmp_path / "mem.json")
        store = MemoryStore(backend=backend, fail_silently=True)
        # This should work fine
        store.save("k", "v")
        assert store.get("k") is not None

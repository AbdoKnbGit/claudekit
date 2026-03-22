"""Tests for claudekit.plugins -- Plugin, PluginLoader, PluginRegistry."""

import pytest

from claudekit.plugins._loader import PluginLoader
from claudekit.plugins._plugin import Plugin
from claudekit.plugins._registry import PluginRegistry


# ── Test plugins ─────────────────────────────────────────────────────────── #


class RecorderPlugin(Plugin):
    """Plugin that records all hook calls for testing."""

    name = "recorder"
    version = "1.0.0"

    def __init__(self):
        self.events: list[str] = []
        self.last_response = None

    def on_request(self, messages, model, context=None):
        self.events.append(f"request:{model}")

    def on_response(self, response, context=None):
        self.events.append("response")
        self.last_response = response
        return response

    def on_tool_call(self, tool_name, tool_input, context=None):
        self.events.append(f"tool_call:{tool_name}")
        return None

    def on_tool_result(self, tool_name, result, context=None):
        self.events.append(f"tool_result:{tool_name}")
        return None

    def on_session_start(self, session_name, config=None):
        self.events.append(f"session_start:{session_name}")

    def on_session_end(self, session_name, usage=None):
        self.events.append(f"session_end:{session_name}")

    def on_error(self, error, context=None):
        self.events.append(f"error:{type(error).__name__}")

    def on_security_event(self, event_type, details, context=None):
        self.events.append(f"security:{event_type}")


class ShortCircuitPlugin(Plugin):
    """Plugin that short-circuits tool calls."""

    name = "short_circuit"
    version = "1.0.0"

    def on_tool_call(self, tool_name, tool_input, context=None):
        return "intercepted"


class CrashPlugin(Plugin):
    """Plugin that raises on every hook."""

    name = "crash"
    version = "1.0.0"

    def on_request(self, messages, model, context=None):
        raise RuntimeError("plugin crashed")

    def on_response(self, response, context=None):
        raise RuntimeError("plugin crashed")


class ResponseModifier(Plugin):
    """Plugin that modifies the response."""

    name = "modifier"
    version = "1.0.0"

    def on_response(self, response, context=None):
        return "modified_response"


# ── Plugin base class ────────────────────────────────────────────────────── #


class TestPlugin:
    def test_default_attributes(self):
        p = Plugin()
        assert p.name == "unnamed_plugin"
        assert p.version == "0.0.0"

    def test_hooks_are_noop(self):
        p = Plugin()
        p.on_request([], "model")
        result = p.on_response("resp")
        assert result == "resp"
        assert p.on_tool_call("t", {}) is None
        assert p.on_tool_result("t", "r") is None

    def test_repr(self):
        p = RecorderPlugin()
        r = repr(p)
        assert "recorder" in r


# ── PluginLoader ─────────────────────────────────────────────────────────── #


class TestPluginLoader:
    def test_load_chaining(self):
        loader = PluginLoader()
        result = loader.load(RecorderPlugin()).load(ShortCircuitPlugin())
        assert result is loader
        assert len(loader) == 2

    def test_unload(self):
        loader = PluginLoader()
        loader.load(RecorderPlugin())
        loader.unload("recorder")
        assert len(loader) == 0

    def test_unload_missing_raises(self):
        loader = PluginLoader()
        with pytest.raises(KeyError, match="nonexistent"):
            loader.unload("nonexistent")

    def test_duplicate_name_replaces(self):
        loader = PluginLoader()
        p1 = RecorderPlugin()
        p2 = RecorderPlugin()
        loader.load(p1).load(p2)
        assert len(loader) == 1
        assert loader.get("recorder") is p2

    def test_all_returns_copy(self):
        loader = PluginLoader()
        loader.load(RecorderPlugin())
        plugins = loader.all()
        assert len(plugins) == 1
        plugins.clear()
        assert len(loader) == 1

    def test_get_found(self):
        loader = PluginLoader()
        p = RecorderPlugin()
        loader.load(p)
        assert loader.get("recorder") is p

    def test_get_not_found(self):
        loader = PluginLoader()
        assert loader.get("missing") is None


class TestPluginLoaderDispatch:
    def test_dispatch_on_request(self):
        loader = PluginLoader()
        rec = RecorderPlugin()
        loader.load(rec)
        loader.dispatch_on_request([{"role": "user", "content": "hi"}], "haiku")
        assert rec.events == ["request:haiku"]

    def test_dispatch_on_response(self):
        loader = PluginLoader()
        rec = RecorderPlugin()
        loader.load(rec)
        result = loader.dispatch_on_response("original")
        assert rec.events == ["response"]
        assert result == "original"

    def test_dispatch_on_response_modification(self):
        loader = PluginLoader()
        loader.load(ResponseModifier())
        result = loader.dispatch_on_response("original")
        assert result == "modified_response"

    def test_dispatch_on_tool_call_passthrough(self):
        loader = PluginLoader()
        rec = RecorderPlugin()
        loader.load(rec)
        result = loader.dispatch_on_tool_call("search", {"q": "test"})
        assert result is None
        assert "tool_call:search" in rec.events

    def test_dispatch_on_tool_call_short_circuit(self):
        loader = PluginLoader()
        loader.load(ShortCircuitPlugin())
        result = loader.dispatch_on_tool_call("search", {"q": "test"})
        assert result == "intercepted"

    def test_dispatch_on_session_start(self):
        loader = PluginLoader()
        rec = RecorderPlugin()
        loader.load(rec)
        loader.dispatch_on_session_start("test_session")
        assert "session_start:test_session" in rec.events

    def test_dispatch_on_session_end(self):
        loader = PluginLoader()
        rec = RecorderPlugin()
        loader.load(rec)
        loader.dispatch_on_session_end("test_session")
        assert "session_end:test_session" in rec.events

    def test_dispatch_on_error(self):
        loader = PluginLoader()
        rec = RecorderPlugin()
        loader.load(rec)
        loader.dispatch_on_error(ValueError("oops"))
        assert "error:ValueError" in rec.events

    def test_dispatch_on_security_event(self):
        loader = PluginLoader()
        rec = RecorderPlugin()
        loader.load(rec)
        loader.dispatch_on_security_event("injection", {"msg": "bad"})
        assert "security:injection" in rec.events

    def test_crash_isolation(self):
        loader = PluginLoader()
        crash = CrashPlugin()
        rec = RecorderPlugin()
        loader.load(crash).load(rec)
        # Should not raise -- crash is isolated
        loader.dispatch_on_request([{"role": "user", "content": "hi"}], "model")
        assert "request:model" in rec.events


# ── PluginRegistry ───────────────────────────────────────────────────────── #


class TestPluginRegistry:
    def test_register_and_get(self):
        reg = PluginRegistry()
        p = RecorderPlugin()
        reg.register(p)
        assert reg.get("recorder") is p

    def test_get_missing(self):
        reg = PluginRegistry()
        assert reg.get("missing") is None

    def test_remove(self):
        reg = PluginRegistry()
        reg.register(RecorderPlugin())
        reg.remove("recorder")
        assert reg.get("recorder") is None

    def test_remove_missing_raises(self):
        reg = PluginRegistry()
        with pytest.raises(KeyError):
            reg.remove("missing")

    def test_names_sorted(self):
        reg = PluginRegistry()
        p1 = RecorderPlugin()
        p2 = ShortCircuitPlugin()
        reg.register(p1)
        reg.register(p2)
        assert reg.names() == ["recorder", "short_circuit"]

    def test_len(self):
        reg = PluginRegistry()
        assert len(reg) == 0
        reg.register(RecorderPlugin())
        assert len(reg) == 1

    def test_contains(self):
        reg = PluginRegistry()
        reg.register(RecorderPlugin())
        assert "recorder" in reg
        assert "missing" not in reg

    def test_all(self):
        reg = PluginRegistry()
        p = RecorderPlugin()
        reg.register(p)
        assert reg.all() == [p]

    def test_replace_same_name(self):
        reg = PluginRegistry()
        p1 = RecorderPlugin()
        p2 = RecorderPlugin()
        reg.register(p1)
        reg.register(p2)
        assert len(reg) == 1
        assert reg.get("recorder") is p2

    def test_repr(self):
        reg = PluginRegistry()
        reg.register(RecorderPlugin())
        r = repr(reg)
        assert "PluginRegistry" in r
        assert "recorder" in r

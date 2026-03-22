"""Tests for claudekit.testing._mock_client -- MockClient zero-API testing."""

import pytest

from claudekit.testing._mock_client import (
    MockClient,
    MockClientUnexpectedCallError,
    MockStreamContext,
)


def _msg(content: str) -> list[dict]:
    return [{"role": "user", "content": content}]


# ── Basic pattern matching ───────────────────────────────────────────────── #


class TestPatternMatching:
    def test_on_text_reply(self):
        client = MockClient()
        client.on("hello", "Hi there!")
        resp = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=100,
            messages=_msg("hello world"),
        )
        assert resp.content[0].text == "Hi there!"

    def test_default_reply(self):
        client = MockClient(strict=False)
        client.default_reply("fallback")
        resp = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=100,
            messages=_msg("anything"),
        )
        assert resp.content[0].text == "fallback"

    def test_strict_mode_raises(self):
        client = MockClient(strict=True)
        with pytest.raises(MockClientUnexpectedCallError):
            client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=100,
                messages=_msg("no match"),
            )

    def test_non_strict_returns_empty(self):
        client = MockClient(strict=False)
        resp = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=100,
            messages=_msg("anything"),
        )
        assert resp.content[0].text == ""

    def test_most_recent_pattern_wins(self):
        client = MockClient()
        client.on("test", "first")
        client.on("test", "second")
        resp = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=100,
            messages=_msg("test"),
        )
        assert resp.content[0].text == "second"


# ── Tool call responses ─────────────────────────────────────────────────── #


class TestToolCall:
    def test_on_tool(self):
        client = MockClient()
        client.on_tool("search", "web_search", {"query": "test"})
        resp = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=100,
            messages=_msg("search for info"),
        )
        assert resp.content[0].type == "tool_use"
        assert resp.content[0].name == "web_search"
        assert resp.content[0].input == {"query": "test"}
        assert resp.stop_reason == "tool_use"


# ── Error simulation ────────────────────────────────────────────────────── #


class TestErrorSimulation:
    def test_on_error(self):
        client = MockClient()
        client.on_error("fail", ValueError)
        with pytest.raises(ValueError, match="Mock error"):
            client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=100,
                messages=_msg("fail now"),
            )


# ── Streaming ────────────────────────────────────────────────────────────── #


class TestStreaming:
    def test_on_stream(self):
        client = MockClient()
        client.on_stream("stream", ["Hello", " ", "world"])
        ctx = client.messages.stream(
            model="claude-haiku-4-5",
            max_tokens=100,
            messages=_msg("stream this"),
        )
        with ctx as stream:
            chunks = [ev.data["text"] for ev in stream]
            assert chunks == ["Hello", " ", "world"]
            final = stream.get_final_message()
            assert final.content[0].text == "Hello world"

    def test_stream_text_property(self):
        ctx = MockStreamContext(["a", "b", "c"], "model", {})
        assert ctx.text == "abc"

    def test_stream_not_entered_raises(self):
        ctx = MockStreamContext(["x"], "model", {})
        with pytest.raises(RuntimeError, match="context manager"):
            list(ctx)

    def test_stream_strict_raises(self):
        client = MockClient(strict=True)
        with pytest.raises(MockClientUnexpectedCallError):
            client.messages.stream(
                model="claude-haiku-4-5",
                max_tokens=100,
                messages=_msg("no match"),
            )


# ── Assertions ───────────────────────────────────────────────────────────── #


class TestAssertions:
    def _make_client(self):
        client = MockClient(strict=False)
        client.default_reply("ok")
        return client

    def test_assert_called(self):
        client = self._make_client()
        client.messages.create(model="m", max_tokens=10, messages=_msg("hi"))
        client.assert_called()

    def test_assert_called_fails(self):
        client = self._make_client()
        with pytest.raises(AssertionError, match="never called"):
            client.assert_called()

    def test_assert_not_called(self):
        client = self._make_client()
        client.assert_not_called()

    def test_assert_not_called_fails(self):
        client = self._make_client()
        client.messages.create(model="m", max_tokens=10, messages=_msg("hi"))
        with pytest.raises(AssertionError):
            client.assert_not_called()

    def test_assert_call_count(self):
        client = self._make_client()
        client.messages.create(model="m", max_tokens=10, messages=_msg("a"))
        client.messages.create(model="m", max_tokens=10, messages=_msg("b"))
        client.assert_call_count(2)

    def test_assert_called_with(self):
        client = self._make_client()
        client.messages.create(model="m", max_tokens=10, messages=_msg("find the answer"))
        client.assert_called_with("find the answer")

    def test_assert_called_with_fails(self):
        client = self._make_client()
        client.messages.create(model="m", max_tokens=10, messages=_msg("hello"))
        with pytest.raises(AssertionError):
            client.assert_called_with("nonexistent")

    def test_assert_model_used(self):
        client = self._make_client()
        client.messages.create(model="claude-haiku-4-5", max_tokens=10, messages=_msg("hi"))
        client.assert_model_used("claude-haiku-4-5")

    def test_assert_model_used_fails(self):
        client = self._make_client()
        client.messages.create(model="haiku", max_tokens=10, messages=_msg("hi"))
        with pytest.raises(AssertionError):
            client.assert_model_used("sonnet")

    def test_assert_call_order(self):
        client = self._make_client()
        client.messages.create(model="m", max_tokens=10, messages=_msg("first"))
        client.messages.create(model="m", max_tokens=10, messages=_msg("second"))
        client.assert_call_order(["first", "second"])

    def test_assert_call_order_fails(self):
        client = self._make_client()
        client.messages.create(model="m", max_tokens=10, messages=_msg("B"))
        client.messages.create(model="m", max_tokens=10, messages=_msg("A"))
        with pytest.raises(AssertionError):
            client.assert_call_order(["A", "B"])


# ── Usage tracking ───────────────────────────────────────────────────────── #


class TestUsageTracking:
    def test_usage_recorded(self):
        client = MockClient(strict=False)
        client.default_reply("hi")
        client.messages.create(model="m", max_tokens=10, messages=_msg("x"))
        assert client.usage.call_count == 1
        assert client.usage.total_tokens > 0

    def test_call_count_property(self):
        client = MockClient(strict=False)
        client.default_reply("hi")
        assert client.call_count == 0
        client.messages.create(model="m", max_tokens=10, messages=_msg("x"))
        assert client.call_count == 1

    def test_calls_returns_copy(self):
        client = MockClient(strict=False)
        client.default_reply("hi")
        client.messages.create(model="m", max_tokens=10, messages=_msg("x"))
        calls = client.calls
        assert len(calls) == 1
        calls.clear()
        assert client.call_count == 1


# ── Reset ────────────────────────────────────────────────────────────────── #


class TestReset:
    def test_reset_clears_everything(self):
        client = MockClient(strict=False)
        client.on("test", "reply")
        client.default_reply("default")
        client.messages.create(model="m", max_tokens=10, messages=_msg("test"))
        client.reset()
        assert client.call_count == 0
        assert client.usage.call_count == 0

    def test_reset_calls_keeps_patterns(self):
        client = MockClient()
        client.on("test", "reply")
        client.messages.create(model="m", max_tokens=10, messages=_msg("test"))
        client.reset_calls()
        assert client.call_count == 0
        # Pattern still works
        resp = client.messages.create(model="m", max_tokens=10, messages=_msg("test"))
        assert resp.content[0].text == "reply"


# ── Token counting ───────────────────────────────────────────────────────── #


class TestTokenCounting:
    def test_default_count(self):
        client = MockClient()
        result = client.messages.count_tokens(model="m", messages=_msg("hi"))
        assert result.input_tokens == 100

    def test_custom_count(self):
        client = MockClient()
        client.mock_token_count(42)
        result = client.messages.count_tokens(model="m", messages=_msg("hi"))
        assert result.input_tokens == 42


# ── Batches ──────────────────────────────────────────────────────────────── #


class TestMockBatches:
    def test_create_and_retrieve(self):
        client = MockClient()
        batch = client.batches.create(requests=[])
        assert "batch_mock_" in batch["id"]
        assert batch["status"] == "completed"
        retrieved = client.batches.retrieve(batch["id"])
        assert retrieved is not None

    def test_cancel(self):
        client = MockClient()
        batch = client.batches.create(requests=[])
        client.batches.cancel(batch["id"])
        assert client.batches.retrieve(batch["id"])["status"] == "cancelled"

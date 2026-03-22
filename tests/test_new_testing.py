"""Verification tests for new testing modules."""
import pytest
from claudekit.testing import (
    create_mock_anthropic, MockTransportHandler,
    MockAgentRunner, MockAgentResult,
    MockSession, MockSessionManager,
    assert_response, assert_agent_result,
    expect,
    ResponseRecorder,
)


class TestMockTransport:
    def test_create_returns_real_anthropic(self):
        import anthropic
        client, handler = create_mock_anthropic()
        assert isinstance(client, anthropic.Anthropic)

    def test_pattern_match(self):
        client, handler = create_mock_anthropic(
            patterns={"weather": "It is sunny."},
        )
        resp = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=100,
            messages=[{"role": "user", "content": "What is the weather?"}],
        )
        assert resp.content[0].text == "It is sunny."

    def test_model_echoed(self):
        client, handler = create_mock_anthropic()
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=50,
            messages=[{"role": "user", "content": "hi"}],
        )
        assert resp.model == "claude-sonnet-4-6"

    def test_default_reply(self):
        client, handler = create_mock_anthropic(default_reply="fallback")
        resp = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=50,
            messages=[{"role": "user", "content": "anything"}],
        )
        assert resp.content[0].text == "fallback"

    def test_usage_present(self):
        client, handler = create_mock_anthropic()
        resp = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=50,
            messages=[{"role": "user", "content": "hi"}],
        )
        assert resp.usage.input_tokens > 0
        assert resp.usage.output_tokens > 0

    def test_call_tracking(self):
        client, handler = create_mock_anthropic()
        client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=50,
            messages=[{"role": "user", "content": "hi"}],
        )
        client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=50,
            messages=[{"role": "user", "content": "bye"}],
        )
        assert len(handler.calls) == 2

    def test_error_pattern(self):
        import anthropic
        client, handler = create_mock_anthropic(
            error_patterns={"bad": (401, "authentication_error", "Invalid key")},
        )
        with pytest.raises(anthropic.AuthenticationError):
            client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=50,
                messages=[{"role": "user", "content": "bad request"}],
            )

    def test_handler_on_method(self):
        client, handler = create_mock_anthropic()
        handler.on("custom", "Custom reply!")
        resp = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=50,
            messages=[{"role": "user", "content": "custom test"}],
        )
        assert resp.content[0].text == "Custom reply!"


class TestExpect:
    def _make_response(self, text="Hello", model="claude-haiku-4-5"):
        client, _ = create_mock_anthropic(default_reply=text)
        return client.messages.create(
            model=model,
            max_tokens=50,
            messages=[{"role": "user", "content": "test"}],
        )

    def test_contains_pass(self):
        resp = self._make_response("Hello world")
        ok, _ = expect.contains("world").evaluate(resp)
        assert ok

    def test_contains_fail(self):
        resp = self._make_response("Hello world")
        ok, msg = expect.contains("xyz").evaluate(resp)
        assert not ok
        assert "FAILED" in msg

    def test_not_contains(self):
        resp = self._make_response("Hello")
        ok, _ = expect.not_contains("xyz").evaluate(resp)
        assert ok

    def test_equals(self):
        resp = self._make_response("exact match")
        ok, _ = expect.equals("exact match").evaluate(resp)
        assert ok

    def test_model_used(self):
        resp = self._make_response(model="claude-sonnet-4-6")
        ok, _ = expect.model_used("claude-sonnet-4-6").evaluate(resp)
        assert ok

    def test_has_text(self):
        resp = self._make_response("some text")
        ok, _ = expect.has_text().evaluate(resp)
        assert ok

    def test_stop_reason(self):
        resp = self._make_response()
        ok, _ = expect.stop_reason("end_turn").evaluate(resp)
        assert ok

    def test_no_tool_call(self):
        resp = self._make_response()
        ok, _ = expect.no_tool_call().evaluate(resp)
        assert ok

    def test_max_tokens(self):
        resp = self._make_response()
        ok, _ = expect.max_tokens(10000).evaluate(resp)
        assert ok

    def test_custom(self):
        resp = self._make_response("Hello")
        ok, _ = expect.custom(lambda r: True, name="always_true").evaluate(resp)
        assert ok


class TestAssertResponse:
    def test_pass(self):
        client, _ = create_mock_anthropic(default_reply="Paris is great")
        resp = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=50,
            messages=[{"role": "user", "content": "test"}],
        )
        assert_response(resp,
            expect.contains("Paris"),
            expect.has_text(),
            expect.stop_reason("end_turn"),
        )

    def test_fail(self):
        client, _ = create_mock_anthropic(default_reply="Hello")
        resp = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=50,
            messages=[{"role": "user", "content": "test"}],
        )
        with pytest.raises(AssertionError, match="FAILED"):
            assert_response(resp, expect.contains("xyz"))


class TestMockAgentRunner:
    def test_pattern_match(self):
        runner = MockAgentRunner()
        runner.on("weather", "It is sunny.")
        result = runner.run("What is the weather?")
        assert result.output == "It is sunny."

    def test_strict_unmatched(self):
        runner = MockAgentRunner(strict=True)
        with pytest.raises(RuntimeError, match="no pattern"):
            runner.run("unknown")

    def test_default_reply(self):
        runner = MockAgentRunner()
        runner.default_reply("default")
        result = runner.run("anything")
        assert result.output == "default"

    def test_call_tracking(self):
        runner = MockAgentRunner()
        runner.default_reply("ok")
        runner.run("a")
        runner.run("b")
        assert runner.call_count == 2

    def test_error_pattern(self):
        runner = MockAgentRunner()
        runner.on_error("fail", ValueError("test error"))
        with pytest.raises(ValueError, match="test error"):
            runner.run("this will fail")


class TestMockSession:
    def test_mock_reply(self):
        session = MockSession("s1")
        session.mock_reply("hello", "Hi there!")
        assert session.run("hello") == "Hi there!"

    def test_pause_raises(self):
        from claudekit.errors import SessionPausedError
        session = MockSession("s1")
        session.pause()
        with pytest.raises(SessionPausedError):
            session.run("test")

    def test_terminate_raises(self):
        from claudekit.errors import SessionTerminatedError
        session = MockSession("s1")
        session.terminate()
        with pytest.raises(SessionTerminatedError):
            session.run("test")

    def test_isolation(self):
        manager = MockSessionManager()
        s1 = manager.create(type("Config", (), {"name": "s1", "model": "claude-haiku-4-5"})())
        s2 = manager.create(type("Config", (), {"name": "s2", "model": "claude-haiku-4-5"})())
        s1.mock_reply("hello", "reply1")
        s2.mock_reply("hello", "reply2")
        assert s1.run("hello") == "reply1"
        assert s2.run("hello") == "reply2"

    def test_manager_status(self):
        manager = MockSessionManager()
        manager.create(type("Config", (), {"name": "s1", "model": "m"})())
        assert manager.status() == {"s1": "running"}

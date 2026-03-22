# claudekit · testing

Zero-API testing utilities for building reliable Claude-powered applications. Test logic, prompt handling, and tool use with zero network calls and zero cost.

**Source files:** `_mock_client.py`, `_mock_transport.py`, `_mock_agent.py`, `_mock_session.py`, `_expect.py`, `_assertions.py`, `_fixtures.py`, `_recorder.py`

---

## Mocks

### `MockClient`
**Source:** `_mock_client.py:472`
A high-level drop-in replacement for `TrackedClient`.
- **Pattern Matching:** Use `.on(substring, reply)` to define responses. Most recently registered patterns take priority.
- **Advanced Mocking:** Supports `on_tool()`, `on_stream()`, and `on_error()`.
- **Verification:** Inspect `.calls` to see every request made, or use `.assert_called_with()`.

### `create_mock_anthropic`
**Source:** `_mock_transport.py:359`
Creates a real `anthropic.Anthropic` client backed by `httpx.MockTransport`.
- **Full Stack:** Unlike `MockClient`, this runs the **entire Anthropic SDK stack** including Pydantic validation, auth headers, and retries.
- **Zero Cost:** No bytes ever touch the wire.
- **Handler:** Returns a `MockTransportHandler` to register patterns after creation.

### `MockAgentRunner` & `MockSession`
**Source:** `_mock_agent.py:47`, `_mock_session.py:29`
Specialized mocks for testing complex workflows.
- **`MockAgentRunner`**: Simulates an `AgentRunner` lifecycle including turns and cost reporting.
- **`MockSession`**: Simulates a managed conversation with `pause()`, `resume()`, and `terminate()` states.

---

## Assertions (`expect`)

The `expect` namespace provides composable assertions designed for LLM outputs.

- **Content:** `expect.contains("Paris")`, `expect.matches(r"\d+")`, `expect.json_valid()`.
- **Usage:** `expect.max_tokens(100)`, `expect.model_used("claude-3-7-sonnet-20250219")`.
- **Tools:** `expect.tool_called("get_weather")`, `expect.tool_called_with("calc", x=5)`.
- **Logic:** `assert_response(response, *assertions)` runs all checks and reports failures together.

---

## Record & Replay

### `ResponseRecorder`
**Source:** `_recorder.py:131`
Captures real interactions for deterministic CI.
1. **Record:** Wrap your real client in `record_mode("path.json")`.
2. **Replay:** Use `replay_mode("path.json")` in your test suite.
- **Deterministic:** Matches requests by a stable hash of their arguments.

---

## Usage Example (Pytest)

```python
import pytest
from claudekit.testing import expect, assert_response

def test_weather_logic(mock_client):
    # 1. Setup mock
    mock_client.on("London", "It is 20 degrees.")
    
    # 2. Run your application code
    response = my_app.ask_about_weather("London")
    
    # 3. Assertions
    assert_response(response,
        expect.contains("20"),
        expect.max_tokens(50)
    )
    mock_client.assert_called_with("London")
```

---

## Technical Details

1. **Construct-based Messages.** `MockClient` uses `anthropic.types.Message.construct()` to avoid Pydantic validation errors when creating messages without a server.
2. **SSE Simulation.** `MockStreamContext` and `_sse_bytes` simulate the Server-Sent Events protocol for testing streaming applications.
3. **Usage Parity.** All mocks integrate with `SessionUsage`, allowing you to test your budget enforcement logic without spending real money.
4. **Pytest Fixtures.** Import `claudekit.testing._fixtures` into your `conftest.py` to get `mock_client`, `mock_anthropic`, and `mock_agent_runner` automatically.
5. **Partial Replay.** `ResponseRecorder` falls back to sequential replay if a hash match fails, helping keep tests passing even after minor prompt tweaks.

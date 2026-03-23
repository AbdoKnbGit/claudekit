---
title: Testing
description: Zero-API testing utilities — MockClient, create_mock_anthropic (realistic httpx transport), MockAgentRunner, MockSession, assertion helpers, and response recording.
module: claudekit.testing
classes: [MockClient, MockAgentRunner, MockSession, MockSessionManager, ResponseRecorder]
exports: [MockClient, create_mock_anthropic, MockAgentRunner, MockAgentResult, MockSession, MockSessionManager, assert_response, assert_agent_result, expect, ResponseRecorder]
---

# Testing

`claudekit.testing` provides two levels of mocking and a suite of assertion helpers — all without making real API calls.

| Tool | What it mocks | Fidelity |
| --- | --- | --- |
| `MockClient` | Drop-in for `TrackedClient` | High-level, no SDK validation |
| `create_mock_anthropic` | httpx transport in real SDK | Full SDK stack (auth, Pydantic, retries) |
| `MockAgentRunner` | Drop-in for `AgentRunner` | Agent result simulation |
| `MockSession` | Drop-in for `Session` | Session lifecycle simulation |

---

## MockClient

Drop-in replacement for `TrackedClient`. Returns genuine `anthropic.types.Message` objects via `construct()` — no network calls.

```python
from claudekit.testing import MockClient

mock = MockClient(
    default_reply="Hello!",           # default response text
    model="claude-haiku-4-5",         # reported model in responses
    strict=False,                     # True: raise MockClientUnexpectedCallError on unmatched call
)

r = mock.messages.create(
    model="claude-haiku-4-5",
    max_tokens=10,
    messages=[{"role": "user", "content": "Hi"}],
)
assert r.content[0].text == "Hello!"
```

### Pattern-based routing

```python
mock = MockClient(default_reply="I don't know.")
mock.on("weather", "It's sunny!")
mock.on("capital of france", "Paris")

# Patterns are substring-matched against the last user message
r = mock.messages.create(
    model="claude-haiku-4-5",
    max_tokens=10,
    messages=[{"role": "user", "content": "What's the weather?"}],
)
assert r.content[0].text == "It's sunny!"
```

### Tool-use responses

```python
mock.on_tool("book flight", "search_flights", {"origin": "JFK", "destination": "CDG"})
mock.on_stream("story", ["Once", " upon", " a time"])
mock.on_error("bad input", ValueError)
```

### Verification

```python
mock.assert_called()                # raises if no calls were made
mock.assert_called_with("weather")  # raises if no call matched "weather"
print(mock.calls)                   # list of all request kwargs received
```

### Streaming

```python
with mock.messages.stream(
    model="claude-haiku-4-5",
    max_tokens=50,
    messages=[{"role": "user", "content": "Tell me a joke"}],
) as stream:
    for event in stream:
        pass  # MockStreamContext iterates text-delta events
    msg = stream.get_final_message()
```

### Usage tracking

`MockClient` has a `.usage` attribute compatible with `TrackedClient`:

```python
mock.usage.call_count
mock.usage.total_tokens
mock.usage.estimated_cost
mock.usage.summary()
```

---

## create_mock_anthropic

Injects a `httpx.MockTransport` into the real `anthropic.Anthropic` client. The **full SDK stack** runs — Pydantic validation, retries, headers — with zero network calls. Most realistic approach.

```python
from claudekit.testing import create_mock_anthropic, MockTransportHandler

client, handler = create_mock_anthropic(
    patterns={"weather": "It's sunny."},
    error_patterns={"bad": (401, "authentication_error", "Invalid key")},
)

# Register more patterns after creation
handler.on("greeting", "Hello!")
handler.on_tool("search", "web_search", {"query": "test"})
handler.on_error("fail", 429, "rate_limit_error", "Too many requests")
handler.on_stream("story", ["Once upon", " a time", "..."])
r = client.messages.create(
    model="claude-haiku-4-5",
    max_tokens=100,
    messages=[{"role": "user", "content": "Capital of France?"}],
)
# r is a fully validated anthropic.types.Message
```

---

## MockAgentRunner

Drop-in for `AgentRunner`.

```python
from claudekit.testing import MockAgentRunner
from claudekit.agents import Agent

agent  = Agent(name="helper", model="claude-haiku-4-5", system="Be helpful.")
runner = MockAgentRunner(agent, default_output="Done!")

result = runner.run("Do this task.")
result.output    # "Done!"
result.turns     # 1
```

---

## MockSession / MockSessionManager

For testing code that uses sessions without spinning up real API clients.

```python
from claudekit.testing import MockSession, MockSessionManager
from claudekit.sessions import SessionConfig

config  = SessionConfig(name="test", model="claude-haiku-4-5")
session = MockSession(config, default_reply="Mocked response")

answer = session.run("Hello")   # "Mocked response"
session.state                   # "running"
session.terminate()
```

---

## Assertions

### assert_response

```python
from claudekit.testing import assert_response

assert_response(
    response,
    contains="Paris",           # str that must appear in the text
    min_length=10,              # minimum text length
    max_length=500,
    model="claude-haiku-4-5",   # expected model
)
```

### assert_agent_result

```python
from claudekit.testing import assert_agent_result

assert_agent_result(
    result,
    contains="Done",
    min_turns=1,
    max_turns=5,
)
```

---

## expect helpers

Assertion builders for common patterns.

```python
from claudekit.testing import expect

# Content
expect.contains("Paris")(response)
expect.matches(r"capital.*france")(response)
expect.json_valid()(response)
expect.has_text()(response)

# Usage
expect.max_tokens(100)(response)
expect.model_used("claude-haiku-4-5")(response)

# Tools
expect.tool_called("get_weather")(response)
expect.tool_called_with("get_weather", city="Paris")(response)
expect.no_tool_called()(response)

# Composable — all assertions evaluated, all failures reported at once
assert_response(response, expect.contains("Paris"), expect.max_tokens(500))
```

---

## ResponseRecorder

Record real API interactions and replay them offline.

```python
from claudekit.testing import ResponseRecorder
from claudekit import TrackedClient

# 1. Record real interactions
client = TrackedClient()
recorder = ResponseRecorder.record_mode(client, path="fixtures/responses.json")
r = recorder.messages.create(
    model="claude-haiku-4-5",
    max_tokens=10,
    messages=[{"role": "user", "content": "Hi"}],
)

# 2. Replay in tests (deterministic, matches by stable hash of args)
replay_client = ResponseRecorder.replay_mode("fixtures/responses.json")
r = replay_client.messages.create(...)
```

---

## Pytest fixtures

```python
# conftest.py
from claudekit.testing._fixtures import mock_client, mock_session_manager

# Usage in tests
def test_something(mock_client):
    mock_client.when("hello").reply("world")
    r = mock_client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=10,
        messages=[{"role": "user", "content": "hello"}],
    )
    assert r.content[0].text == "world"
```

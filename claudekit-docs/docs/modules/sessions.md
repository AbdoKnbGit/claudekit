# Sessions

**Module:** `claudekit.sessions` · **Classes:** `SessionManager`, `Session`, `SessionConfig`, `MultiSessionUsage`

`claudekit.sessions` wraps `TrackedClient` with full conversation lifecycle management: states (`running`, `paused`, `finished`, `error`), cost/turn limits, callbacks, and multi-session aggregation.

## Quick start

```python
from claudekit import TrackedClient
from claudekit.sessions import SessionManager, SessionConfig

client  = TrackedClient()
manager = SessionManager(client)

config  = SessionConfig(
    name="user-42",
    model="claude-sonnet-4-6",
    max_cost_usd=0.50,
    max_turns=20,
)
session = manager.create(config)
answer  = session.run("What is 2 + 2?")   # "4"
session.terminate()
```

---

## SessionConfig

Declarative configuration for a session. Validated at construction.

```python
from claudekit.sessions import SessionConfig

config = SessionConfig(
    name="my-session",                     # required, unique
    model="claude-sonnet-4-6",             # required
    system="You are a helpful assistant.", # optional system prompt
    memory=None,                           # MemoryStore | None
    security=None,                         # SecurityLayer | None
    tools=None,                            # list of tool defs | None
    max_cost_usd=1.00,                     # budget cap (USD)
    max_turns=50,                          # turn limit
    timeout_seconds=30,                    # per-call wall-clock timeout
    platform="anthropic",                  # "anthropic" | "bedrock" | "vertex"
    tags=["production", "user-facing"],    # for filtering
    shared_context={"user_id": "u42"},     # accessible in callbacks
    on_cost_warning=my_callback,           # (name, cost, limit) -> None, fires at 80%
    on_error=my_error_handler,             # (name, error) -> None
    ignore_broadcasts=False,
)
```

**Raises `ConfigurationError`** if: name is empty, model is empty, `max_cost_usd <= 0`, `max_turns <= 0`, `timeout_seconds <= 0`, or `platform` is not one of the valid values.

---

## Session

Session instances are created by `SessionManager.create()`.

### Properties

```python
session.name         # str — unique session name
session.state        # str — "running" | "paused" | "finished" | "error"
session.config       # SessionConfig
session.usage        # SessionUsage — token counts + cost for this session
session.turn_count   # int — completed API call count
```

### Lifecycle

```python
session.pause()      # block further calls; raises SessionTerminatedError if finished
session.resume()     # unblock; raises SessionTerminatedError if finished/error
session.terminate()  # final; sets state="finished", no further calls possible
```

### Making calls

```python
# Convenience: sends a single user prompt, returns assistant text
answer = session.run("Explain quantum entanglement.")

# Full control via the messages proxy
response = session.messages.create(
    messages=[{"role": "user", "content": "Hello"}],
    max_tokens=512,
    # model, system, tools are injected from SessionConfig automatically
)

# Streaming
with session.messages.stream(
    messages=[{"role": "user", "content": "Write a poem"}],
    max_tokens=1024,
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)
```

**Calls raise automatically when:**
- `state == "paused"` → `SessionPausedError`
- `state in ("finished", "error")` → `SessionTerminatedError`
- `usage.estimated_cost >= max_cost_usd` → `SessionBudgetExceededError`
- `turn_count >= max_turns` → `SessionTerminatedError`


---

## SessionManager

Creates and manages multiple sessions.

```python
from claudekit.sessions import SessionManager

manager = SessionManager(client)
```

### create

```python
session = manager.create(config)
# Raises SessionNameConflictError if a non-terminated session with the same name exists
```

### get / list

```python
session = manager.get("user-42")          # Session | None
all_sessions = manager.all()              # list[Session] — in creation order
all_sessions = manager.list()             # alias for all()
tagged = manager.by_tag("production")     # list[Session] — filter by tag
```

### Lifecycle control

```python
manager.pause("user-42")             # pause by name
manager.resume("user-42")            # resume by name
manager.terminate("user-42")         # terminate by name
manager.terminate_all()              # terminate every session
```

### Status and usage

```python
status = manager.status()
# dict: {name: {state, turns, cost, model, tags}}

multi_usage = manager.usage          # MultiSessionUsage
multi_usage.total_cost               # float — sum across all sessions
multi_usage.total_tokens             # int
multi_usage.call_count               # int
multi_usage.per_session              # dict[name, SessionUsage]
```

### Broadcast

```python
manager.broadcast("reload-config", {"version": 2})
# Delivers event to every session whose ignore_broadcasts=False
# Sessions can read events via session.event_queue
```

---

## MultiSessionUsage

Aggregated usage across all sessions managed by a `SessionManager`.

```python
usage = manager.usage

usage.total_cost      # float
usage.total_tokens    # int
usage.call_count      # int
usage.per_session     # dict[str, SessionUsage]
```

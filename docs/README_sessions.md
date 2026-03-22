# claudekit · sessions

Managed conversation lifecycles with budget enforcement, turn limits, and multi-session orchestration.

**Source files:** `_config.py`, `_session.py`, `_manager.py`, `_aggregator.py`

---

## Core Components

### `SessionConfig`
**Source:** `_config.py:19`
A declarative dataclass defining the rules for a session.
- **Budgets:** `max_cost_usd` and `max_turns`.
- **Defaults:** `model`, `system` prompt, and `tools`.
- **Callbacks:** `on_cost_warning` (fires at 80% budget) and `on_error`.
- **Metadata:** `tags` for filtering and `shared_context` for custom state.

### `Session`
**Source:** `_session.py:108`
A managed conversation wrapping a `TrackedClient`.
- **`run(prompt)`**: High-level helper for one-shot text interactions.
- **`messages.create() / .stream()`**: Proxies that inject session defaults and enforce budgets *before* the API call.
- **Lifecycle:** Transitions between `running`, `paused`, `finished`, and `error`.
- **Budgeting:** Raises `SessionBudgetExceededError` if the cost limit is reached and transitions the session to `error`.

### `SessionManager`
**Source:** `_manager.py:27`
The central registry for multiple sessions.
- **`create(config)`**: Instantiates and tracks a new session.
- **`by_tag(tag)`**: Filters active sessions by metadata tags.
- **`broadcast_event(event, data)`**: Delivers an event to all non-terminated sessions (useful for context updates).
- **`usage`**: Returns a `MultiSessionUsage` aggregator for the entire manager.

---

## Usage Example

```python
from claudekit.client import TrackedClient
from claudekit.sessions import SessionManager, SessionConfig

client = TrackedClient()
manager = SessionManager(client)

# Configure a session with a $0.50 budget
config = SessionConfig(
    name="research_task",
    model="claude-3-7-sonnet-20250219",
    max_cost_usd=0.50,
    tags=["research", "long-running"]
)

session = manager.create(config)
answer = session.run("Compare Rust and C++ memory safety.")

# Check status of all sessions
print(manager.status()) # {"research_task": "running"}
```

---

## Technical Details

1. **Lazy Cost Tracking.** For streaming calls, the session cannot know the final cost until the stream is fully consumed. The `PostCallStreamWrapper` handles turn increments and cost checks once the generator exits.
2. **Thread Safety.** `Session` and `SessionManager` use `threading.Lock` to ensure state transitions and event delivery are safe in multi-threaded environments.
3. **Usage Isolation.** Each `Session` gets its own `SessionUsage` instance. The underlying `TrackedClient` is cloned via `.with_options()` so that its global usage tracker is NOT affected by individual session spend.
4. **Event Deque.** Each session maintains a fixed-size `event_queue` (default maxlen=1000) for received broadcasts. This queue can be inspected by tools or plugins during execution.
5. **Session Persistence.** `SessionManager` keeps sessions in memory. To persist sessions across application restarts, you must manually serialize the `config` and `usage` data.

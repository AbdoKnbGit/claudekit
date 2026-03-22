# claudekit · agents

Declarative agent definitions, high-level execution runners, and inspection tools for the Claude Agent SDK.

**Source files:** `_agent.py`, `_runner.py`, `_budget.py`, `_hooks.py`, `_inspector.py`

---

## Core Components

### `Agent`
**Source:** `_agent.py:26`
A declarative specification of an agent's identity and configuration.
- **Identity:** `name`, `model`, `system` prompt.
- **Capabilities:** `tools`, `skills`.
- **Governance:** `max_turns`, `max_cost_usd`, `permission_mode`, `effort`.
- **Environment:** `platform`, `timeout_seconds`.

### `AgentRunner`
**Source:** `_runner.py:88`
The execution engine that bridges `claudekit` definitions with the `claude_agent_sdk.query()` implementation.
- **`run(prompt)`**: Synchronous execution.
- **`run_async(prompt)`**: Asynchronous execution.
- **`stream(prompt)`**: Async generator yielding raw SDK messages.
- **`resume(session_id, prompt)`**: Continues an existing session.

### `BudgetGuard`
**Source:** `_budget.py:18`
A protective wrapper for `AgentRunner` that tracks cumulative usage across multiple calls.
- **Cumulative Limits:** Enforces `max_cost_usd` and `max_turns` across the entire lifecycle of the guard.
- **Warnings:** Fires `on_warn` callbacks at specific thresholds (e.g., 80% budget).
- **Safety:** Raises `BudgetExceededError` before starting a run if the budget is already exhausted.

### `HookBuilder`
**Source:** `_hooks.py:20`
A factory for creating SDK-compatible event hooks.
- **`block_tool(name)`**: Prevents specific tools from being called.
- **`audit_log(path)`**: Appends every internal event to a JSONL file.
- **`require_confirmation(name)`**: Pauses execution for user approval (supports CLI `input()` or custom callbacks).
- **`inject_context(name, extra)`**: Merges dynamic metadata into tool inputs at runtime.

### `AgentInspector`
**Source:** `_inspector.py:22`
A debugging wrapper that records every message, tool call, and token metric.
- **`print()`**: Renders a formatted timeline of the agent's work to the terminal.
- **`export_json(path)`**: Saves the full execution trace for later analysis.

---

## Usage Example

```python
from claudekit.agents import Agent, AgentRunner, BudgetGuard, AgentInspector

# 1. Define the Agent
agent = Agent(
    name="researcher",
    model="claude-3-7-sonnet-20250219",
    system="You are a research assistant.",
    max_cost_usd=1.0 # $1.00 hard limit
)

# 2. Wrap with instrumentation and protection
runner = AgentRunner(agent)
inspector = AgentInspector(runner)
guard = BudgetGuard(inspector, max_cost_usd=1.0)

# 3. Execute
result = guard.run("Summarise the 2024 AI safety guidelines.")

# 4. Debug
inspector.print()
```

---

## Technical Details

1. **SDK Field Mapping.** `AgentRunner` maps `Agent` fields to the `ClaudeAgentOptions` expected by the subprocess-based SDK. It handles field name differences (e.g., `max_cost_usd` -> `max_budget_usd`).
2. **Subprocess Isolation.** The Claude Agent SDK often runs in a separate process. As a result, Python callables passed in `agent.tools` cannot be executed by the SDK directly. `AgentRunner` logs a warning if callables are detected; use `TrackedClient` for native Python tool support.
3. **Async Loops.** `AgentRunner.run()` includes logic to detect if it's already inside an event loop and uses a `ThreadPoolExecutor` to avoid "loop already running" errors.
4. **Token/Cost Reporting.** The Agent SDK typically returns a `ResultMessage` containing `total_cost_usd` and `num_turns`. `AgentResult` captures these fields for reporting.
5. **Hook Incompatibility.** Hooks produced by `HookBuilder` are designed for the event structure of the Agent SDK. They are **not** compatible with the `claudekit.plugins` module, which uses a different lifecycle model.

---
title: Agents
description: Agent definition dataclass, AgentRunner (Claude Agent SDK subprocess bridge), AgentInspector, BudgetGuard, and HookBuilder.
module: claudekit.agents
classes: [Agent, AgentRunner, AgentResult, AgentInspector, BudgetGuard, HookBuilder]
---

# Agents

`claudekit.agents` provides the declarative `Agent` dataclass and `AgentRunner` — a bridge to the Claude Agent SDK subprocess. Use `AgentRunner` for multi-turn agentic loops; use `TrackedClient` for simple single-turn API calls.

## Agent

Declarative definition of an agent. Holds no runtime state.

```python
from claudekit.agents import Agent

agent = Agent(
    name="researcher",                # required, unique
    model="claude-sonnet-4-6",        # default: DEFAULT_MODEL
    system="You are a researcher.",   # system prompt
    tools=[],                         # list of @tool-decorated functions
    allowed_tools=None,               # list[str] — SDK allow-list
    disallowed_tools=None,            # list[str] — SDK deny-list
    permission_mode="default",        # "default" | "acceptEdits" | "plan" | "bypassPermissions"
    max_turns=20,                     # int | None
    max_cost_usd=1.0,                 # float | None — per-agent budget
    effort="medium",                  # "low" | "medium" | "high" | "max"
    memory=None,                      # MemoryStore | None
    security=None,                    # SecurityLayer | None
    skills=[],                        # list[Skill]
    platform="anthropic",             # "anthropic" | "bedrock" | "vertex" | "foundry"
    timeout_seconds=None,             # int | None
    metadata={},                      # arbitrary dict for tagging
)
```

**Raises `ConfigurationError`** if: name is empty, effort/permission_mode/platform is invalid, max_cost_usd or max_turns <= 0.

---

## AgentRunner

Executes an `Agent` via the Claude Agent SDK subprocess. Requires `pip install claude-agent-sdk`.

```python
from claudekit.agents import AgentRunner

runner = AgentRunner(
    agent=agent,
    hooks=None,         # dict[str, list[callable]] | None — SDK hook dict
    sdk_kwargs={},      # extra ClaudeAgentOptions kwargs
)

result = runner.run("Summarize the top AI papers from 2025.")
print(result.output)
```

> **Note:** `runner.run()` is a sync wrapper — it calls `asyncio.run()` internally. The underlying SDK uses a subprocess, so Python `@tool` functions attached to the agent cannot be passed into the subprocess. Use `TrackedClient` with tools for Python-callable tools.

### AgentResult

```python
result.output            # str — final text response
result.turns             # int — conversation turns consumed
result.total_tokens      # int — token count for the run
result.total_cost        # float — USD cost for the run
result.duration_seconds  # float — wall-clock time
result.messages          # list — raw messages from the SDK
result.session_id        # str | None — SDK session ID for resuming
```

### Resuming a session

```python
result1 = runner.run("Start a research task.")
result2 = runner.run("Continue from where we left off.", session_id=result1.session_id)
```

---

## AgentInspector

Wraps an `AgentRunner` and captures the full message trace for debugging.

```python
from claudekit.agents import Agent, AgentRunner, AgentInspector

agent    = Agent(name="demo", model="claude-sonnet-4-6", system="Be helpful.")
runner   = AgentRunner(agent)
inspector = AgentInspector(runner)

result = inspector.run("Explain quantum tunnelling.")

inspector.print()          # pretty-print full trace to stdout
data = inspector.to_dict() # dict — machine-readable trace
inspector.export_json("trace.json")  # write JSON to file

inspector.messages         # list[dict] — raw message trace
inspector.turn_summaries   # list[dict] — per-turn summaries
```

---

## BudgetGuard

Enforces per-call cost and turn limits. Typically used by `Orchestrator` and `AgentRunner` internally, but can be used standalone.

```python
from claudekit.agents import BudgetGuard

guard = BudgetGuard(
    max_cost_usd=0.50,       # hard stop when cost exceeds this
    warn_cost_usd=0.40,      # fire on_warning callback at this threshold
    max_turns=10,
    on_warning=lambda info: print(f"Warning: {info}"),  # callback dict with cost/turns info
)
guard.record_call(cost=0.01, tokens=500)
guard.check()   # raises BudgetExceededError or AgentMaxTurnsError if limits reached

guard.total_cost          # float
guard.total_turns         # int
guard.remaining_cost_usd  # float | None
```

---

## HookBuilder

Fluent builder for hook dicts compatible with `TrackedClient.messages.create()`.

> **Note:** `HookBuilder` produces a list format that is **not** compatible with the Claude Agent SDK subprocess format. Use `HookBuilder` hooks only with `TrackedClient`, not `AgentRunner`.

```python
from claudekit.agents import HookBuilder

hooks = (
    HookBuilder()
    .on_tool_call(lambda name, inp: print(f"Tool: {name}"))
    .on_tool_result(lambda name, res: print(f"Result: {res}"))
    .build()
)
```

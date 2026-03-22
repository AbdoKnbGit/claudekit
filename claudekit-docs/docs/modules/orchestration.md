---
title: Orchestration
description: Orchestrator manages named Agent definitions, routes tasks to them via RuleRouter/LLMRouter/ManualRouter, handles agent-to-agent delegation, and aggregates cost.
module: claudekit.orchestration
classes: [Orchestrator, RuleRouter, LLMRouter, ManualRouter, OrchestrationResult]
---

# Orchestration

`claudekit.orchestration` provides the `Orchestrator` — the central control plane for multi-agent workflows. It routes tasks to the right agent, handles agent-to-agent delegation, detects loops, and enforces a cost ceiling.

## Quick start

```python
from claudekit.agents import Agent
from claudekit.orchestration import Orchestrator, RuleRouter

support = Agent(name="support", model="claude-haiku-4-5", system="You handle support.")
billing = Agent(name="billing", model="claude-haiku-4-5", system="You handle billing.")

orch = Orchestrator(
    router=RuleRouter(
        {"billing": [r"invoice", r"charge", r"refund"]},
        default="support",
    ),
    max_total_cost_usd=5.0,
)
orch.register(support)
orch.register(billing)

result = await orch.run("Why was I double-charged?")
print(result.final_output)
print(f"Cost: ${result.total_cost:.4f}")
```

---

## Orchestrator

```python
from claudekit.orchestration import Orchestrator

orch = Orchestrator(
    router=None,                     # any router | None (must pass entry_agent= if None)
    max_delegation_depth=5,          # DelegationLoopError after this many hops
    max_total_cost_usd=None,         # BudgetExceededError when breached
    runner_kwargs={},                # forwarded to every AgentRunner
)
```

### Agent registry

```python
orch.register(agent)          # ConfigurationError if name already exists
orch.unregister("billing")    # KeyError if not found
orch.agents                   # dict[str, Agent] — read-only copy
```

### run

Async. Routes to entry agent, handles delegation chain, returns aggregated result.

```python
result = await orch.run(
    task="Explain my invoice",
    entry_agent="billing",     # optional; uses router if None
    context={"user_id": "u42"},
)
```

**Raises:**
- `OrchestratorError` — no agents registered, unknown entry agent, no router and no entry agent.
- `DelegationLoopError` — delegation depth exceeded `max_delegation_depth`.
- `BudgetExceededError` — total cost breached `max_total_cost_usd`.

### run_parallel

Run multiple tasks concurrently, each independently routed.

```python
results = await orch.run_parallel(
    tasks=["Task A", "Task B", "Task C"],
    entry_agent="worker",     # optional; uses router per-task if None
    context=None,
)
# Returns list[OrchestrationResult]
# Failed tasks have errors != {} in their result
```

---

## OrchestrationResult

Returned by `orch.run()` and each element of `orch.run_parallel()`.

```python
result.final_output        # str — text from the last agent in the chain
result.agent_trace         # list[dict] — [{agent, prompt, output, ...}, ...]
result.total_cost          # float — USD
result.total_tokens        # int
result.duration_seconds    # float
result.errors              # dict[int, Exception] — task_index -> error (parallel runs)

result.succeeded           # bool — True if errors is empty
result.failed_task_indices # list[int] — indices with errors
result.agents_used         # list[str] — agent names in order
```

---

## Routers

All routers implement `async route(task: str, agents: dict) -> str`.

### RuleRouter

Evaluates keyword/regex rules in order. First match wins.

```python
from claudekit.orchestration import RuleRouter

router = RuleRouter(
    rules={
        "billing": [r"invoice", r"charge", r"refund", r"payment"],
        "technical": [r"bug", r"error", r"crash", r"not working"],
    },
    default="support",   # agent name to use when no rule matches (None = raise OrchestratorError)
)
```

- Patterns are compiled as case-insensitive regex.
- `default=None` raises `OrchestratorError` when no rule matches.

### LLMRouter

Sends a classification prompt to a lightweight model. Haiku by default.

```python
from claudekit.orchestration import LLMRouter

router = LLMRouter(
    model="claude-haiku-4-5",   # classifier model
    system=None,                 # override the system prompt
    temperature=0.0,
)
```

Falls back to the first registered agent if `claude_agent_sdk` is not installed.

### ManualRouter

Developer-supplied routing function. May be sync or async.

```python
from claudekit.orchestration import ManualRouter

def my_router(task: str, agents: dict) -> str:
    if "urgent" in task.lower():
        return "priority-agent"
    return "default-agent"

router = ManualRouter(my_router)
```

---

## Agent delegation

Any agent registered in the orchestrator automatically receives a `delegate_to_agent` tool. The agent can call it to hand the task off to another agent. The orchestrator detects the delegation, routes the prompt to the new agent, and continues the chain until no more delegation occurs.

The chain is capped at `max_delegation_depth` (default 5) to prevent loops.

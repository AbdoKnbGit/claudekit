# claudekit · orchestration

Multi-agent coordination, intelligent routing, and delegation management.

**Source files:** `_orchestrator.py`, `_router.py`, `_result.py`

---

## Core Components

### `Orchestrator`
**Source:** `_orchestrator.py:29`
The central control plane for multi-agent workflows.
- **Agent Registry:** Manage any number of `Agent` definitions.
- **Automatic Delegation:** Injects a `delegate_to_agent` tool into every participant. Agents can hand off to siblings by calling this tool.
- **Loop Protection:** Configurable `max_delegation_depth` (default: 5) prevents circular hand-offs.
- **Cost Ceiling:** Hard limit on aggregate dollar spend across the entire chain of agents.
- **Execution Modes:** 
  - `run()`: Sequential execution with delegation support.
  - `run_parallel()`: Discrete tasks executed concurrently with failure isolation.

### `BaseRouter`
**Source:** `_router.py:30`
Abstract interface for routing strategies. Subclasses implement `route(task, agents) -> str`.

- **`LLMRouter`**: Uses a fast model (e.g., Claude Haiku) to classify the user's task and select the best agent based on their names.
- **`RuleRouter`**: Keyword and regex-based routing. Perfect for deterministic dispatching (e.g., "billing" keyword routes to the billing agent).
- **`ManualRouter`**: Developer-supplied callback for arbitrary routing logic (e.g., database lookups or session-based routing).

### `OrchestrationResult`
**Source:** `_result.py:14`
An aggregated summary of the orchestration.
- **`final_output`**: The response from the last agent in the chain.
- **`agent_trace`**: A step-by-step history of which agents were called, their prompts, and their outputs.
- **Metrics:** Cumulative `total_cost` and `total_tokens`.
- **`errors`**: Mapping of task indices to exceptions for failed parallel runs.

---

## Usage Example

```python
from claudekit.agents import Agent
from claudekit.orchestration import Orchestrator, RuleRouter

# 1. Define specialist agents
writer = Agent(name="writer", system="You write technical articles.")
editor = Agent(name="editor", system="You review and refine articles.")

# 2. Setup Orchestrator with keyword routing
orch = Orchestrator(
    router=RuleRouter({"writer": ["write", "create"], "editor": ["review", "fix"]})
)
orch.register(writer)
orch.register(editor)

# 3. Execute (Writer will finish their task, then delegate to Editor)
result = await orch.run("Write an article about Python 3.14 and then have it reviewed.")
print(f"Final Outcome: {result.final_output}")
print(f"Workflow Chain: {result.agents_used}")
```

---

## Technical Details

1. **Tool Injection.** The `delegate_to_agent` tool is dynamically constructed based on the current list of registered agents. It uses an `enum` in the JSON Schema to force the model to select a valid sibling.
2. **Parallel Isolation.** In `run_parallel()`, a failure in one branch (e.g., a timeout or budget limit) does **not** stop other branches. The specific error is captured in the results list.
3. **Trace Preservation.** The `agent_trace` captures the `session_id` for every intermediate step, allowing the developer to resume specific agent conversations later if needed.
4. **Different Platforms.** An orchestrator can coordinate agents running on different platforms (e.g., one on Anthropic, another on Bedrock) since platform configuration is encapsulated within the `Agent` definition.
5. **Context Propagation.** The `context` dictionary passed to `run()` is forwarded to every agent in the delegation chain, ensuring shared state (like user preferences) persists across hand-offs.

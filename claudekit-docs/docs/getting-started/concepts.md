---
title: Core Concepts
description: The mental model behind claudekit — how TrackedClient, Skills, Sessions, Security, Memory, and Orchestration relate to each other.
---

# Core Concepts

## The mental model

claudekit sits between your application and the Anthropic SDK. It intercepts every API call to add observability, security, and memory — then passes the call through unchanged.

```
Your app
  │
  ▼
TrackedClient  ←── SecurityLayer (policies run on every request/response)
  │            ←── MemoryStore   (optional memory injection)
  │            ←── PluginLoader  (lifecycle hooks: logging, alerts, OTel)
  ▼
anthropic.Anthropic (real SDK, unchanged)
  │
  ▼
Anthropic API
```

## TrackedClient

`TrackedClient` is the core primitive. It wraps `anthropic.Anthropic` (or the async variant) and records `CallRecord` objects for every response — model used, tokens in/out, cache hits, cost, request ID, and duration.

```python
client = TrackedClient(api_key="sk-...")
# client.messages.create(...)  ← identical to the real SDK
# client.usage.summary()       ← available after any call
# client.usage.breakdown()     ← per-model breakdown
```

## Skills

A `Skill` is a portable AI capability: a named bundle of system prompt, model, tools, output format, and optional memory/security. Skills are the primary unit of composition in claudekit.

```python
skill = Skill(name="scanner", system="...", model="claude-haiku-4-5")
result = await skill.run(input="...", client=client)
```

Skills can be attached to agents, combined in pipelines, and shared across projects.

## Sessions

A `Session` wraps a `TrackedClient` with lifecycle state (`running`, `paused`, `finished`, `error`), per-session budget enforcement, and turn counting. Sessions are created through `SessionManager` and identified by name.

```python
mgr     = SessionManager(client=client)
session = mgr.create(SessionConfig(name="user-42", model="claude-sonnet-4-6",
                                    max_cost_usd=0.50, max_turns=20))
session.messages.create(messages=[{"role": "user", "content": "Hello"}])
session.terminate()
```

## Security

`SecurityLayer` holds an ordered list of `Policy` objects. Before every API call, `check_request()` runs all policies on the message list. After every call, `check_response()` runs all policies on the response. Any policy can raise a typed `SecurityError` subclass.

```python
layer = SecurityLayer([
    Policy.no_prompt_injection(),
    Policy.no_pii_in_output(),
    Policy.rate_limit(requests_per_minute=30),
])
```

Policies are composable and stateless. Presets (`DeveloperToolsPreset`, `CustomerFacingPreset`, etc.) bundle opinionated combinations.

## Memory

`MemoryStore` is a key-value store with scopes, TTL, and full-text search. It delegates storage to a pluggable `AbstractBackend` (SQLite or JSON file). Entries persist across process restarts when using `SQLiteBackend`.

```python
mem = MemoryStore(backend=SQLiteBackend("~/.myapp/mem.db"))
mem.save("key", "value", scope="scope-name", ttl_seconds=3600)
mem.get("key", scope="scope-name")
mem.search("injection", scope="security", limit=10)
```

## Orchestration

`Orchestrator` manages named `Agent` definitions and routes tasks to them. Agents can delegate to each other using a built-in `delegate_to_agent` tool. The orchestrator detects delegation loops and enforces a global cost ceiling.

Three router strategies are built in:
- `RuleRouter` — keyword/regex rules, evaluated in order
- `LLMRouter` — uses a lightweight model to classify
- `ManualRouter` — developer-supplied function

## Plugins

`PluginLoader` is a lifecycle hook system. Plugins implement `on_request`, `on_response`, `on_tool_call`, `on_security_event`, and session lifecycle events. Built-in plugins: `LoggingPlugin`, `CostAlertPlugin`, `OpenTelemetryPlugin`.

## Error hierarchy

Every exception is a subclass of `ClaudekitError`. Each carries `message`, `code` (machine-readable), `context` (dict of diagnostic data), and `recovery_hint`.

```
ClaudekitError
├── SecurityError
│   ├── PromptInjectionError
│   ├── PIIDetectedError
│   ├── JailbreakDetectedError
│   ├── OutputValidationError
│   └── ToolBlockedError
├── BudgetError
│   ├── BudgetExceededError
│   ├── RateLimitError
│   └── TokenLimitError
├── AgentError
│   ├── AgentTimeoutError
│   ├── AgentMaxTurnsError
│   └── DelegationLoopError
├── ClaudekitMemoryError
│   ├── MemoryBackendError
│   └── MemoryValueTooLargeError
├── SessionError
│   ├── SessionPausedError
│   ├── SessionTerminatedError
│   ├── SessionNameConflictError
│   └── SessionBudgetExceededError
├── BatchError
│   ├── BatchNotReadyError
│   ├── BatchCancelledError
│   └── BatchPartialFailureError
├── ConfigurationError
│   ├── MissingAPIKeyError
│   └── DeprecatedModelError
└── OrchestratorError
```

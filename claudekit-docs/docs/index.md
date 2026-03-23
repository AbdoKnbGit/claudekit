# claudekit Documentation

claudekit is a production-grade Python framework built on top of the Anthropic SDK. It does not replace the SDK — it extends it with the infrastructure every real application needs.

## What claudekit provides

| Layer | Capability |
| --- | --- |
| **Models** | Model registry with pricing, capabilities, aliases, and task-based selection via `select_model()` |
| **Observability** | Per-call token and cost tracking, CSV export, per-model breakdown |
| **Security** | Request/response policy pipeline with 8 built-in policies and 5 presets |
| **Memory** | Persistent key-value store with SQLite/JSON backends and full-text search |
| **Skills** | Portable, reusable AI capability bundles |
| **Sessions** | Managed conversation sessions with lifecycle states and budget enforcement |
| **Agents** | Multi-turn agent runner with timeout, budget guard, and inspector |
| **Orchestration** | Multi-agent routing with auto-delegation and cycle detection |
| **Batches** | Batch API submission, polling, cost tracking |
| **Thinking** | Extended thinking helpers for Opus and Sonnet 4+ |
| **Plugins** | Lifecycle hooks for logging, alerting, and OpenTelemetry |
| **Testing** | Mock clients, scripted responses, and typed assertion helpers |
| **Precheck** | Free pre-flight token counting via the count_tokens API |
| **Prompts** | Versioned prompt management with diff and rollback |
| **Errors** | 30+ typed exceptions with machine-readable codes and recovery hints |

## Navigation

### Getting Started
- [Installation](getting-started/installation.md) — pip install, requirements, platform extras
- [Quickstart](getting-started/quickstart.md) — running your first tracked call in 5 minutes
- [Core Concepts](getting-started/concepts.md) — mental model, key abstractions

### Module Reference
- [Client](modules/client.md) — `TrackedClient`, `AsyncTrackedClient`, platform clients
- [Models](modules/models.md) — model registry, pricing, `select_model`
- [Security](modules/security.md) — `SecurityLayer`, policies, presets
- [Memory](modules/memory.md) — `MemoryStore`, backends, `context_with_memory`
- [Skills](modules/skills.md) — `Skill`, `SkillRegistry`, prebuilt skills
- [Sessions](modules/sessions.md) — `SessionManager`, `SessionConfig`, `MultiSessionUsage`
- [Tools](modules/tools.md) — `@tool`, `ToolRegistry`, prebuilt tools
- [Thinking](modules/thinking.md) — `thinking_enabled`, `thinking_adaptive`, `extract_thinking`
- [Plugins](modules/plugins.md) — `PluginLoader`, `LoggingPlugin`, `CostAlertPlugin`, `OpenTelemetryPlugin`
- [Orchestration](modules/orchestration.md) — `Orchestrator`, `RuleRouter`, `LLMRouter`, `ManualRouter`
- [Agents](modules/agents.md) — `Agent`, `AgentRunner`, `BudgetGuard`, `AgentInspector`
- [Batches](modules/batches.md) — `BatchBuilder`, `BatchManager`
- [Precheck](modules/precheck.md) — `TokenCounter`
- [Prompts](modules/prompts.md) — `PromptManager`
- [Testing](modules/testing.md) — `MockClient`, `MockAgentRunner`, `create_mock_anthropic`
- [Errors](modules/errors.md) — full exception hierarchy

### API Reference
- [Full API Reference](api-reference/index.md)

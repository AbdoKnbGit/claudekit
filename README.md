<div align="center">

<img src="Logo.png" alt="claudekit logo" width="120" />

# claudekit

**Everything the Anthropic SDK is missing — in one coherent Python framework.**

*Track costs. Enforce policies. Build agents. Ship faster.*

[![License MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.1.1-brightgreen.svg)](pyproject.toml)
[![Python ≥3.10](https://img.shields.io/badge/python-%3E%3D3.10-3776ab.svg)](pyproject.toml)
[![Anthropic SDK](https://img.shields.io/badge/anthropic--sdk-%3E%3D0.86-orange.svg)](pyproject.toml)
[![Agent SDK](https://img.shields.io/badge/agent--sdk-supported-purple.svg)](claudekit-docs/docs/modules/agents.md)
[![MCP](https://img.shields.io/badge/MCP-supported-red.svg)](claudekit-docs/docs/modules/tools.md)

[Installation](#installation) · [Quick Start](#quick-start) · [What's Inside](#whats-inside) · [Platforms](#platforms) · [Documentation](#documentation)

</div>

---

## Installation

```bash
pip install claudekit
pip install claudekit[agent]   # Agent SDK support
pip install claudekit[mcp]     # MCP server builder
pip install claudekit[otel]    # OpenTelemetry tracing
pip install claudekit[all]     # Everything
```

---

## Quick Start

```python
from claudekit import TrackedClient

client = TrackedClient()
response = client.messages.create(
    model="claude-haiku-4-5",
    max_tokens=256,
    messages=[{"role": "user", "content": "Hello"}],
)
print(client.usage.summary())
# tokens_in=10  tokens_out=24  cost=$0.000042  calls=1
```

---

## What's Inside

| Module | What it does |
|---|---|
| `claudekit.client` | Tracked sync/async clients for Anthropic, Bedrock, Vertex, Foundry |
| `claudekit.security` | Typed policy pipeline — injection, jailbreak, PII, rate limits, budget caps |
| `claudekit.memory` | Persistent memory store with SQLite + FTS5, injected into context automatically |
| `claudekit.sessions` | Named sessions with config, lifecycle hooks, and aggregated usage |
| `claudekit.agents` | Declarative agents with budget guards and full message trace inspection |
| `claudekit.orchestration` | Multi-agent routing — rule-based, LLM-based, or manual |
| `claudekit.tools` | `@tool` decorator, tool registry, MCP server builder |
| `claudekit.skills` | Portable skill bundles — summarizer, classifier, extractor, reviewer, researcher |
| `claudekit.batches` | Fluent batch API with polling, cancellation, and cost stats |
| `claudekit.prompts` | Versioned prompt storage with A/B comparison |
| `claudekit.testing` | `MockClient`, `MockAgentRunner`, `expect.*` assertions, record/replay |
| `claudekit.plugins` | Lifecycle hooks — logging, cost alerts, OpenTelemetry |
| `claudekit.thinking` | Extended thinking helpers and token budget guidance |
| `claudekit.precheck` | Pre-flight token counting with cost estimates |

---

| Capability | `anthropic` SDK | claude agent sdk | claudekit |
|---|---|---|---|
| Send messages to API | ✅ core purpose | ❌ goes via CLI subprocess | ✅ TrackedClient |
| Streaming (SSE) | ✅ built-in | ✅ async generator | ✅ tracked wrapper |
| Tool use / function calling | ✅ manual loop | ✅ built-in (Bash, Read, Write…) | ✅ `@tool` decorator + ToolRegistry |
| MCP server integration | ✅ via API connector | ✅ native | ✅ MCPServer builder |
| Bedrock / Vertex / Foundry | ✅ AnthropicBedrock | ❌ Anthropic API only | ✅ TrackedBedrockClient, TrackedVertexClient, TrackedFoundryClient |
| **Cost tracking per call** | ❌ read usage yourself | ⚠️ `total_cost_usd` only at the very end of a run | ✅ per-call `duration_ms`, `cost`, `request_id`, `cache_tokens` — live |
| **Running cost budget cap** | ❌ | ❌ `max_budget_usd` on full run only | ✅ per-session and per-agent, fires at 80% warning |
| **Persistent memory** | ❌ | ❌ write files manually | ✅ SQLite + FTS5, TTL, LRU eviction, scoped namespacing |
| **Security policy pipeline** | ❌ | ❌ infrastructure-level only (containers, VMs) | ✅ injection, PII, jailbreak, rate-limit — in Python, before any API call |
| **Session lifecycle** | ❌ | ❌ | ✅ pause / resume / terminate + budget enforcement |
| **Multi-session usage aggregation** | ❌ | ❌ | ✅ `all_sessions_usage.summary()` across all tenants |
| **Plugin lifecycle hooks** | ❌ | ⚠️ PreToolUse / PostToolUse only | ✅ `on_request`, `on_response`, `on_tool_call`, `on_session_start`, `on_error`, `on_security_event` |
| **Prompt versioning + A/B testing** | ❌ | ❌ | ✅ `PromptManager` with diff, compare(), and template rendering |
| **Batch management** | ⚠️ raw API only | ❌ | ✅ `BatchManager` with polling, cancellation, sidecar persistence, 50% cost discount |
| **Skill bundles with Pydantic output** | ❌ | ❌ | ✅ `Skill(output_format=MyModel)` → returns validated dataclass, not raw text |
| **Multi-agent routing** | ❌ | ⚠️ model decides via Task tool | ✅ `RuleRouter` / `LLMRouter` / `ManualRouter` — you control the routing |
| **Pre-flight token counting** | ✅ `count_tokens()` (raw) | ❌ | ✅ `TokenCounter` with `fits_in_context`, `percent_used`, cost estimate |
| **Extended thinking helpers** | ✅ raw params only | ❌ | ✅ `thinking_enabled()` / `thinking_adaptive()` with validation |
| **Deprecated model warnings** | ❌ | ❌ | ✅ `DeprecatedModelWarning` fires on `messages.create()` automatically |
 
---
## Documentation

**[Full Documentation →](claudekit-docs/docs/index.md)**

---

## License

[MIT](LICENSE)

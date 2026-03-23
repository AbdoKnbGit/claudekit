---
title: API Reference
description: Complete symbol index for every public class, function, and constant in claudekit. Cross-references to module documentation.
---

# API Reference

Complete index of every public symbol in claudekit v0.1.0. Click any module link to read the full documentation.

---

## claudekit (top-level)

```python
from claudekit import TrackedClient, AsyncTrackedClient, create_client
from claudekit import TrackedBedrockClient, TrackedVertexClient, TrackedFoundryClient
```

---

## claudekit.client → [Client docs](../modules/client.md)

| Symbol | Type | Description |
| --- | --- | --- |
| `create_client()` | function | Auto-detect platform from env vars, returns matching client |
| `TrackedClient` | class | Sync Anthropic SDK wrapper with usage tracking |
| `AsyncTrackedClient` | class | Async variant of TrackedClient |
| `TrackedBedrockClient` | class | AWS Bedrock variant |
| `TrackedVertexClient` | class | Google Vertex AI variant |
| `TrackedFoundryClient` | class | Azure AI Foundry variant |
| `SessionUsage` | class | Usage tracker attached to every client |
| `CallRecord` | dataclass | Per-call record: tokens, cost, duration, request ID |

---

## claudekit.models → [Models docs](../modules/models.md)

| Symbol | Type | Description |
| --- | --- | --- |
| `MODELS` | `list[Model]` | All models including deprecated |
| `MODELS_BY_ID` | `dict[str, Model]` | Lookup by API ID or alias |
| `get_model(id)` | function | Returns `Model` by ID or alias |
| `select_model(task)` | function | Returns API ID for a `ModelTask` |
| `ModelTask` | enum | `SIMPLE`, `BALANCED`, `SMART`, `FAST`, `THINKING` |
| `Model` | dataclass | Frozen model definition with pricing and capabilities |

---

## claudekit.security → [Security docs](../modules/security.md)

| Symbol | Type | Description |
| --- | --- | --- |
| `SecurityLayer` | class | Ordered policy pipeline applied to every call |
| `Policy` | class | Factory class with static methods for all built-in policies |
| `InputSanitizerPolicy` | class | Strip HTML/scripts, truncate inputs |
| `PromptInjectionPolicy` | class | Detect prompt injection heuristics |
| `JailbreakPolicy` | class | Detect jailbreak attempts |
| `PIIPolicy` | class | Redact or block PII in responses |
| `OutputSchemaPolicy` | class | Validate JSON output against a schema |
| `RateLimitPolicy` | class | Per-user or global rate limiting |
| `BudgetCapPolicy` | class | Block after cost threshold exceeded |
| `ToolGuardPolicy` | class | Block tool calls matching glob patterns |
| `DeveloperToolsPreset` | function | injection + jailbreak + rate_limit(120/min) |
| `CustomerFacingPreset` | function | sanitizer + injection + jailbreak + PII + rate_limit(30/min) |
| `FinancialServicesPreset` | function | All policies + strict budget + PII block |
| `HealthcarePreset` | function | PII block + injection + output schema |
| `InternalToolsPreset` | function | injection + rate_limit(300/min) + tool_guard |

---

## claudekit.memory → [Memory docs](../modules/memory.md)

| Symbol | Type | Description |
| --- | --- | --- |
| `MemoryStore` | class | Backend-agnostic memory store |
| `MemoryEntry` | dataclass | Single memory record with TTL and metadata |
| `SQLiteBackend` | class | SQLite + FTS5 backend (recommended) |
| `JSONFileBackend` | class | JSON file backend (development) |
| `AbstractBackend` | class | Base class for custom backends |
| `context_with_memory` | function | Enrich message list with relevant memories |

---

## claudekit.skills → [Skills docs](../modules/skills.md)

| Symbol | Type | Description |
| --- | --- | --- |
| `Skill` | dataclass | Portable capability bundle |
| `SkillRegistry` | class | Named skill lookup registry |
| `SummarizerSkill` | class | Pre-built summarization skill |
| `ClassifierSkill` | class | Pre-built text classification skill |
| `DataExtractorSkill` | class | Pre-built structured data extraction |
| `CodeReviewerSkill` | class | Pre-built code review skill |
| `ResearcherSkill` | class | Pre-built research skill |

---

## claudekit.sessions → [Sessions docs](../modules/sessions.md)

| Symbol | Type | Description |
| --- | --- | --- |
| `SessionManager` | class | Create and manage multiple sessions |
| `Session` | class | Single managed conversation session |
| `SessionConfig` | dataclass | Declarative session configuration |
| `MultiSessionUsage` | class | Aggregated usage across all sessions |

---

## claudekit.tools → [Tools docs](../modules/tools.md)

| Symbol | Type | Description |
| --- | --- | --- |
| `tool` | decorator | Convert Python function to Anthropic tool definition |
| `ToolWrapper` | class | Callable wrapper with `.to_dict()` and `.name` |
| `ToolRegistry` | class | Named tool registry with `.to_anthropic_format()` and `.to_agent_sdk_format()` |
| `MCPServer` | class | stdio MCP server from `@tool` functions — `.run()`, `.run_background()`, `.to_options_dict()` |
| `ToolInputValidator` | class | JSON Schema validation with type coercion |
| `read_file` | `ToolWrapper` | Pre-built: read file contents |
| `write_file` | `ToolWrapper` | Pre-built: write file contents |
| `list_files` | `ToolWrapper` | Pre-built: list directory |
| `run_python` | `ToolWrapper` | Pre-built: execute Python code |
| `run_shell` | `ToolWrapper` | Pre-built: execute shell command |
| `http_get` | `ToolWrapper` | Pre-built: HTTP GET |
| `http_post` | `ToolWrapper` | Pre-built: HTTP POST |
| `parse_json` | `ToolWrapper` | Pre-built: parse JSON string |
| `format_table` | `ToolWrapper` | Pre-built: format data as table |

---

## claudekit.thinking → [Thinking docs](../modules/thinking.md)

| Symbol | Type | Description |
| --- | --- | --- |
| `thinking_enabled(budget_tokens)` | function | Returns `{"type": "enabled", "budget_tokens": N}` |
| `thinking_adaptive(budget_tokens)` | function | Returns `{"type": "adaptive", "budget_tokens": N}` |
| `thinking_disabled()` | function | Returns `{"type": "disabled"}` |
| `extract_thinking(response)` | function | Returns `(thoughts: str, answer: str)` |

---

## claudekit.plugins → [Plugins docs](../modules/plugins.md)

| Symbol | Type | Description |
| --- | --- | --- |
| `PluginLoader` | class | Manages and dispatches hooks to all loaded plugins |
| `Plugin` | class | Base class for custom plugins |
| `LoggingPlugin` | class | Structured logging for all lifecycle events |
| `CostAlertPlugin` | class | Callback when cost threshold exceeded |
| `OpenTelemetryPlugin` | class | OTel spans for requests, tools, sessions |

---

## claudekit.orchestration → [Orchestration docs](../modules/orchestration.md)

| Symbol | Type | Description |
| --- | --- | --- |
| `Orchestrator` | class | Multi-agent control plane |
| `RuleRouter` | class | Keyword/regex routing rules |
| `LLMRouter` | class | LLM-based task classification |
| `ManualRouter` | class | Developer-supplied routing function |
| `OrchestrationResult` | dataclass | Aggregated run result |

---

## claudekit.agents → [Agents docs](../modules/agents.md)

| Symbol | Type | Description |
| --- | --- | --- |
| `Agent` | dataclass | Declarative agent definition |
| `AgentRunner` | class | Execute agent via Claude Agent SDK subprocess |
| `AgentResult` | dataclass | Run outcome |
| `AgentInspector` | class | Capture full message trace for debugging |
| `BudgetGuard` | class | Enforce cost and turn limits |
| `HookBuilder` | class | Fluent hook dict builder (for TrackedClient) |

---

## claudekit.batches → [Batches docs](../modules/batches.md)

| Symbol | Type | Description |
| --- | --- | --- |
| `BatchBuilder` | class | Fluent batch request constructor |
| `BatchManager` | class | Submit, poll, cancel, retrieve batch results |
| `BatchResult` | dataclass | Full batch result with items and stats |
| `BatchStats` | dataclass | Aggregate counts and cost |

---

## claudekit.precheck → [Precheck docs](../modules/precheck.md)

| Symbol | Type | Description |
| --- | --- | --- |
| `TokenCounter` | class | Pre-flight token counting |
| `TokenCountResult` | dataclass | Count result with cost estimate and warnings |

---

## claudekit.prompts → [Prompts docs](../modules/prompts.md)

| Symbol | Type | Description |
| --- | --- | --- |
| `PromptManager` | class | Versioned prompt storage and comparison |
| `PromptVersion` | dataclass | Single prompt version with template |
| `ComparisonResult` | dataclass | A/B comparison outputs and costs |

---

## claudekit.testing → [Testing docs](../modules/testing.md)

| Symbol | Type | Description |
| --- | --- | --- |
| `MockClient` | class | Drop-in TrackedClient mock with pattern routing |
| `MockClientUnexpectedCallError` | exception | Raised in strict mode on unmatched call |
| `MockStreamContext` | class | Mock streaming context manager |
| `create_mock_anthropic` | function | Realistic mock via httpx.MockTransport |
| `MockTransportHandler` | class | Configure responses for transport mock |
| `MockAgentRunner` | class | Drop-in AgentRunner mock |
| `MockAgentResult` | dataclass | Pre-configured agent result |
| `MockSession` | class | Drop-in Session mock |
| `MockSessionManager` | class | Drop-in SessionManager mock |
| `assert_response` | function | Assert properties of an API response |
| `assert_agent_result` | function | Assert properties of an AgentResult |
| `expect` | module | Composable assertion builders |
| `ResponseRecorder` | class | Record/replay real API interactions |

---

## claudekit.errors → [Errors docs](../modules/errors.md)

All exception classes. See [Errors](../modules/errors.md) for the full hierarchy and handling patterns.

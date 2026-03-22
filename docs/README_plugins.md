# claudekit · plugins

Lifecycle-hook plugin framework for extending `claudekit` behavior. Plugins can intercept and modify requests, responses, tool calls, and session data, or provide side-channel functionality like logging and monitoring.

**Source files:** `_plugin.py`, `_loader.py`, `_registry.py`, `_prebuilt.py`

---

## Class: `Plugin`

**Source:** `_plugin.py:30`

The base class for all plugins. Subclass this and override the hooks you need.

### Attributes

| Attribute | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | `"unnamed_plugin"` | Unique identifier for the plugin. |
| `version` | `str` | `"0.0.0"` | SemVer version string. |

### Lifecycle Hooks

All hooks are optional and provide no-op defaults.

#### Request / Response
- **`on_request(messages, model, context=None) -> None`**: Called before the API request. `messages` is mutable (modifying it affects the outgoing request).
- **`on_response(response, context=None) -> Any`**: Called after receiving a response. Must return the response (modified or original).

#### Tools
- **`on_tool_call(tool_name, tool_input, context=None) -> Any`**: Called before execution. Return a non-`None` value to short-circuit the tool and use that value as the result.
- **`on_tool_result(tool_name, result, context=None) -> Any`**: Called after execution. Return a non-`None` value to replace the original result.

#### Sessions
- **`on_session_start(session_name, config=None) -> None`**: Called when a session is initialized.
- **`on_session_cost_update(session_name, cost_usd, usage=None) -> None`**: Called whenever cost/usage is recorded in the session.
- **`on_session_end(session_name, usage=None) -> None`**: Called when a session context manager exits.

#### System
- **`on_error(error, context=None) -> None`**: Called when any exception is raised in the pipeline.
- **`on_security_event(event_type, details, context=None) -> None`**: Called for security-related triggers (e.g., PII detected, prompt injection blocked).

---

## Class: `PluginLoader`

**Source:** `_loader.py:24`

Manages the active pipeline of plugins and dispatches hooks in registration order.

### Methods

#### `load(plugin) -> PluginLoader`
Loads a plugin instance. This method is **fluent** (returns `self`). If a plugin with the same name exists, it is replaced.

#### `unload(name) -> None`
Removes a plugin by name. Raises `KeyError` if not found.

#### `get(name) -> Optional[Plugin]` / `all() -> list[Plugin]`
Retrieves loaded plugin(s).

#### `dispatch_*(...)`
Internal methods used by `claudekit` components (Client, Session, Tools) to trigger hooks. 
- **Safe Dispatch:** All hook calls are wrapped in `_safe_call`. If a plugin raises an exception, it is caught and logged, and the rest of the pipeline continues.

---

## Class: `PluginRegistry`

**Source:** `_registry.py:29`

A global dictionary-like registry for plugin discovery. Useful for managing available plugins separately from the active `PluginLoader`.

---

## Pre-built Plugins

### `LoggingPlugin`
**Source:** `_prebuilt.py:19`
Provides structured logging for all lifecycle events.
- **`include_content` (bool)**: If `True`, logs the first 100 characters of messages/responses. Defaults to `False` for security.

### `CostAlertPlugin`
**Source:** `_prebuilt.py:93`
Triggers a callback when USD cost thresholds are met.
- **`threshold_usd` (float)**: The budget limit.
- **`per_session` (bool)**: If `True`, alerts on per-session cost; if `False`, alerts on global cumulative cost.

### `OpenTelemetryPlugin`
**Source:** `_prebuilt.py:161`
Creates OTel spans for requests, tool calls, and sessions.
- **No-op Mode:** If the `opentelemetry` package is not installed, this plugin silently becomes a no-op instead of raising `ImportError`.

---

## Module Exports (`__all__`)

| Name | Type | Description |
|---|---|---|
| `Plugin` | class | Base class for customization |
| `PluginLoader` | class | Active hook dispatcher |
| `PluginRegistry` | class | Discovery registry |
| `LoggingPlugin` | class | Pre-built logging |
| `CostAlertPlugin` | class | Pre-built budget alerts |
| `OpenTelemetryPlugin` | class | Pre-built tracing |

---

## Edge Cases & Gotchas

1. **Mutation in `on_request`.** Modifying the `messages` list in `on_request` directly affects what is sent to Anthropic. Ensure your modifications are valid API messages.

2. **Modification in `on_response`.** If you replace the `response` object, ensure it maintains the same interface (e.g., has `.content`, `.model`, `.usage` attributes) that subsequent plugins or the application expect.

3. **Plugin Order.** Plugins are executed in the order they were `.load()`-ed. For `on_response`, this means earlier plugins see the raw response, and later plugins see the result of earlier plugins.

4. **Exception Masking.** Because `PluginLoader` catches all exceptions (`Exception`), a buggy plugin might fail silently in your application logic. Check your logs for `claudekit.plugins` error messages.

5. **Tool Short-circuiting.** If `on_tool_call` returns a non-`None` value, the actual tool function is **never called**. This is useful for caching or mocking tool results.

6. **Shared Context.** The `context` dictionary passed to hooks is consistent across a single request/response cycle, allowing you to pass data between `on_request` and `on_response`.

---
title: Plugins
description: PluginLoader and lifecycle hook system. Built-in plugins for structured logging, cost alerts, and OpenTelemetry tracing.
module: claudekit.plugins
classes: [PluginLoader, Plugin, LoggingPlugin, CostAlertPlugin, OpenTelemetryPlugin]
---

# Plugins

`claudekit.plugins` provides a lifecycle hook system. Plugins receive events at every stage of the API pipeline: requests, responses, tool calls, sessions, costs, errors, and security events.

## PluginLoader

Manages plugin registration and dispatches hooks in load order. A failing plugin is caught and logged — it never breaks the pipeline.

```python
from claudekit.plugins import PluginLoader, LoggingPlugin, CostAlertPlugin

loader = (
    PluginLoader()
    .load(LoggingPlugin(include_content=False))
    .load(CostAlertPlugin(threshold_usd=5.0, callback=lambda c, s: print(f"Alert: ${c:.2f}")))
)
```

### Plugin management

```python
loader.load(plugin)          # add plugin (fluent, returns self; replaces if same name)
loader.unload("plugin-name") # remove by name
loader.plugins               # list[Plugin] — registered plugins in load order
```

### PluginRegistry

Separate registry for dynamic plugin discovery separate from the loader.

```python
from claudekit.plugins import PluginRegistry

registry = PluginRegistry()
registry.register(my_plugin)
registry.unregister("my_plugin")
plugin = registry.get("my_plugin")   # Plugin | None
all_plugins = registry.all()         # list[Plugin]
```

### Dispatch methods

Called by `TrackedClient` automatically on each API call.

```python
loader.dispatch_on_request(messages, model="claude-haiku-4-5", context=None)
loader.dispatch_on_response(response, context=None)       # returns (possibly modified) response
loader.dispatch_on_tool_call(tool_name, tool_input, context=None)
loader.dispatch_on_tool_result(tool_name, result, context=None)
loader.dispatch_on_session_start(session_name, config=None)
loader.dispatch_on_session_cost_update(session_name, cost_usd, usage=None)
loader.dispatch_on_session_end(session_name, usage=None)
loader.dispatch_on_error(error, context=None)
loader.dispatch_on_security_event(event_type, details, context=None)
```

---

## Built-in Plugins

### LoggingPlugin

Structured logging for all lifecycle events.

```python
from claudekit.plugins import LoggingPlugin
import logging

plugin = LoggingPlugin(
    logger_instance=logging.getLogger("myapp"),  # default: "claudekit.plugin.logging"
    level="INFO",          # any valid logging level string
    include_content=False, # True: log message content (risk of logging sensitive data)
)
```

Hooks implemented: `on_request`, `on_response`, `on_tool_call`, `on_tool_result`, `on_session_start`, `on_session_cost_update`, `on_session_end`, `on_error`, `on_security_event`.

### CostAlertPlugin

Fires a callback exactly once when cumulative cost exceeds a threshold.

```python
from claudekit.plugins import CostAlertPlugin

def alert(cost_usd: float, session_name: str) -> None:
    send_slack_alert(f"Claude cost ${cost_usd:.2f} in session {session_name}")

plugin = CostAlertPlugin(
    threshold_usd=1.00,      # alert at $1.00
    callback=alert,          # (cost_usd, session_name) -> None
    per_session=False,       # True: track per session; False: global total
)
```

### OpenTelemetryPlugin

Creates OpenTelemetry spans for requests, tool calls, and sessions. No-op if `opentelemetry` is not installed — never raises `ImportError`.

```python
from claudekit.plugins import OpenTelemetryPlugin

plugin = OpenTelemetryPlugin(service_name="my-service")
# Uses the global OTel tracer provider.
# Spans: claude.request.<model>, claude.tool.<name>, claude.session.<name>

# Or pass a custom tracer:
from opentelemetry import trace
tracer = trace.get_tracer("custom-tracer")
plugin = OpenTelemetryPlugin(tracer=tracer)
```

---

## Writing a Custom Plugin

Override only the hooks you need.

```python
from claudekit.plugins import Plugin
from typing import Any

class AuditPlugin(Plugin):
    name = "audit"
    version = "1.0.0"

    def on_request(self, messages: list[dict], model: str, context: Any = None) -> None:
        audit_log.write(f"REQUEST model={model} msgs={len(messages)}")

    def on_response(self, response: Any, context: Any = None) -> Any:
        audit_log.write(f"RESPONSE model={response.model}")
        return response   # must return response (possibly modified)

    def on_security_event(self, event_type: str, details: dict, context: Any = None) -> None:
        audit_log.write(f"SECURITY {event_type}: {details}")

    def on_error(self, error: Exception, context: Any = None) -> None:
        audit_log.write(f"ERROR {type(error).__name__}: {error}")
```

### Hook signatures

| Hook | Signature | Notes |
| --- | --- | --- |
| `on_request` | `(messages, model, context)` | Before API call |
| `on_response` | `(response, context) -> response` | Must return response |
| `on_tool_call` | `(tool_name, tool_input, context) -> None\|result` | Return non-None to short-circuit |
| `on_tool_result` | `(tool_name, result, context) -> None\|replacement` | Return non-None to replace result |
| `on_session_start` | `(session_name, config)` | |
| `on_session_cost_update` | `(session_name, cost_usd, usage)` | |
| `on_session_end` | `(session_name, usage)` | |
| `on_error` | `(error, context)` | |
| `on_security_event` | `(event_type, details, context)` | |

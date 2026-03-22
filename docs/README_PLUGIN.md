# claudekit / plugins -- Architecture, API & Tests

Full reference for `claudekit/plugins/`, covering every class and method,
with a complete walkthrough of `test_plugin.py` and its 120-test run.

---

## Module layout

```
claudekit/plugins/
    __init__.py    -- public exports + lazy imports for pre-built plugins
    _plugin.py     -- Plugin base class (9 hooks)
    _loader.py     -- PluginLoader (lifecycle management + dispatch)
    _registry.py   -- PluginRegistry (named discovery store)
    _prebuilt.py   -- LoggingPlugin, CostAlertPlugin, OpenTelemetryPlugin
```

Public imports:

```python
from claudekit.plugins import Plugin, PluginLoader, PluginRegistry
from claudekit.plugins import LoggingPlugin, CostAlertPlugin, OpenTelemetryPlugin
```

`LoggingPlugin`, `CostAlertPlugin`, and `OpenTelemetryPlugin` are **lazy-loaded**
via `__getattr__` — they are only imported from `_prebuilt.py` when accessed.

---

## Architecture diagram

```
                +------------------+
                |   Your Code      |
                +------------------+
                        |
              loader.dispatch_on_*(...)
                        |
                +------------------+
                |  PluginLoader    |  <-- load() / unload() / get() / all()
                +------------------+
                |  _plugins: list  |
                +--[p1][p2][p3]----+
                    |   |   |
                    v   v   v
              hooks called in load order
              each hook: _safe_call() -- exceptions caught + logged
```

**Key dispatch semantics:**

| Hook | Return behaviour |
|---|---|
| `on_request` | void — all plugins called |
| `on_response` | chain — each non-None return replaces the response |
| `on_tool_call` | short-circuit — first non-None return stops the chain |
| `on_tool_result` | chain — each non-None return replaces the result |
| `on_session_start` | void — all plugins called |
| `on_session_cost_update` | void — all plugins called |
| `on_session_end` | void — all plugins called |
| `on_error` | void — all plugins called |
| `on_security_event` | void — all plugins called |

---

## Plugin (base class, `_plugin.py`)

```python
class Plugin:
    name:    str = "unnamed_plugin"
    version: str = "0.0.0"
```

Override only the hooks you need. All hooks have safe no-op defaults.

### Hook signatures and default returns

```python
def on_request(self, messages: list[dict], model: str, context: dict | None) -> None
def on_response(self, response: Any, context: dict | None) -> Any          # returns response
def on_tool_call(self, tool_name: str, tool_input: dict, context) -> Any   # returns None
def on_tool_result(self, tool_name: str, result: Any, context) -> Any      # returns None
def on_session_start(self, session_name: str, config: dict | None) -> None
def on_session_cost_update(self, session_name: str, cost_usd: float, usage) -> None
def on_session_end(self, session_name: str, usage: dict | None) -> None
def on_error(self, error: Exception, context: dict | None) -> None
def on_security_event(self, event_type: str, details: dict, context) -> None
```

`__repr__` returns `PluginName(name='...', version='...')`.

### Minimal custom plugin

```python
class AuditPlugin(Plugin):
    name    = "audit"
    version = "1.0.0"

    def on_request(self, messages, model, context=None):
        print(f"[audit] {len(messages)} messages -> {model}")

    def on_error(self, error, context=None):
        print(f"[audit] ERROR: {error}")
```

---

## PluginLoader (`_loader.py`)

Manages the plugin pipeline. Plugins are called **in load order**.

```python
loader = PluginLoader()
```

### Management methods

```python
loader.load(plugin)       # add plugin; returns self (fluent); duplicate name -> replaces
loader.unload("name")     # remove by name; raises KeyError if not found
loader.get("name")        # -> Plugin | None
loader.all()              # -> list[Plugin], shallow copy
len(loader)               # -> int
repr(loader)              # -> "PluginLoader(plugins=[...])"
```

**Fluent chaining:**

```python
loader = (
    PluginLoader()
    .load(LoggingPlugin())
    .load(CostAlertPlugin(threshold_usd=1.0, callback=alert))
    .load(OpenTelemetryPlugin())
)
```

**Duplicate name** — if `load()` is called with a plugin whose `name` already
exists, the old plugin is removed and the new one appended (with a WARNING log).

### Dispatch methods

All dispatchers are safe: `_safe_call()` catches and logs exceptions from any
individual plugin, so a broken plugin never crashes the pipeline.

```python
loader.dispatch_on_request(messages, model, context=None)       -> None
loader.dispatch_on_response(response, context=None)             -> Any  # (possibly modified)
loader.dispatch_on_tool_call(tool_name, tool_input, context)    -> Any  # short-circuit or None
loader.dispatch_on_tool_result(tool_name, result, context)      -> Any  # (possibly replaced)
loader.dispatch_on_session_start(session_name, config=None)     -> None
loader.dispatch_on_session_cost_update(session_name, cost, usage) -> None
loader.dispatch_on_session_end(session_name, usage=None)        -> None
loader.dispatch_on_error(error, context=None)                   -> None
loader.dispatch_on_security_event(event_type, details, context) -> None
```

### `_safe_call` internals

```python
def _safe_call(self, plugin, hook_name, *args, **kwargs) -> Any:
    try:
        return getattr(plugin, hook_name)(*args, **kwargs)
    except (AttributeError, TypeError, ValueError, RuntimeError):
        logger.exception(...)
        return None
```

Only catches `AttributeError, TypeError, ValueError, RuntimeError` —
other exceptions (e.g. `KeyboardInterrupt`, `SystemExit`) propagate normally.

---

## PluginRegistry (`_registry.py`)

Separate named store for **discovery** — decoupled from the active pipeline.

```python
registry = PluginRegistry()
registry.register(plugin)          # key = plugin.name; duplicate -> replaces (warning)
registry.get("name")               # -> Plugin | None
registry.all()                     # -> list[Plugin], insertion order
registry.remove("name")            # -> None; raises KeyError if not found
registry.names()                   # -> list[str], sorted
len(registry)                      # -> int
"name" in registry                 # -> bool
repr(registry)                     # -> "PluginRegistry(plugins=[...])"
```

**Difference from PluginLoader:**
- `PluginLoader` **runs** plugins (dispatch hooks).
- `PluginRegistry` **stores** plugins for discovery (no hooks fired).
- Both support duplicate-replace semantics.

---

## LoggingPlugin (`_prebuilt.py`)

```python
LoggingPlugin(
    logger_instance=None,   # default: logging.getLogger("claudekit.plugin.logging")
    level="INFO",           # logging level for all hooks
    include_content=False,  # True = log message content (careful with sensitive data)
)
```

- `name = "logging"`, `version = "1.0.0"`
- Logs every hook event at the configured level
- `on_error` always logs at `ERROR` level regardless of the `level` setting
- `on_response` returns the response unchanged

**Log messages:**

| Hook | Message format |
|---|---|
| `on_request` | `Request: model=..., messages=N[, content=...]` |
| `on_response` | `Response: model=..., in=N, out=N` |
| `on_tool_call` | `Tool call: <name>` |
| `on_tool_result` | `Tool result: <name>` |
| `on_session_start` | `Session started: <name>` |
| `on_session_cost_update` | `Session <name> cost: $X.XXXX` |
| `on_session_end` | `Session ended: <name>` |
| `on_error` | `Error: ExcType: message` (at ERROR level) |
| `on_security_event` | `Security event: <type> <details>` |

---

## CostAlertPlugin (`_prebuilt.py`)

```python
CostAlertPlugin(
    threshold_usd=1.00,           # alert threshold in USD
    callback=None,                # callable(cost_usd, session_name)
    per_session=False,            # True = per-session tracking
)
```

- `name = "cost_alert"`, `version = "1.0.0"`
- Only reacts to `on_session_cost_update` — other hooks are no-ops
- Alert fires **once** per threshold crossing (not on every subsequent call)

### Global mode (`per_session=False`, default)

```python
cap = CostAlertPlugin(threshold_usd=0.05, callback=my_alert)
# Accumulates cost across ALL sessions
cap.on_session_cost_update("A", 0.03)  # _global_cost = 0.03, no alert
cap.on_session_cost_update("A", 0.04)  # _global_cost = 0.07 >= 0.05 -> alert!
cap.on_session_cost_update("A", 0.10)  # _alerted_global=True -> silent
```

### Per-session mode (`per_session=True`)

```python
psc = CostAlertPlugin(threshold_usd=0.03, callback=my_alert, per_session=True)
# Each session has its own tracker and fires independently
psc.on_session_cost_update("sess-A", 0.04)   # sess-A alert!
psc.on_session_cost_update("sess-B", 0.01)   # sess-B below, no alert
psc.on_session_cost_update("sess-B", 0.05)   # sess-B alert!
psc.on_session_cost_update("sess-A", 0.99)   # sess-A already alerted, silent
```

**Internal state:**

```python
cap._global_cost          # float  -- cumulative (global mode only)
cap._session_costs        # dict[str, float]  -- per-session (per_session mode)
cap._alerted_global       # bool   -- global mode one-shot flag
cap._alerted_sessions     # set[str]  -- per-session one-shot flags
```

---

## OpenTelemetryPlugin (`_prebuilt.py`)

```python
OpenTelemetryPlugin(
    tracer=None,                  # custom OTel tracer; None = auto-detect
    service_name="claudekit",     # tracer name if auto-creating
)
```

- `name = "opentelemetry"`, `version = "1.0.0"`
- **No-op** if `opentelemetry` package is not installed — never raises `ImportError`
- Creates spans for `on_request`, `on_tool_call`, `on_session_start`
- `_otel_available = False` when OTel is absent

```python
plugin = OpenTelemetryPlugin(service_name="my-app")
plugin._otel_available  # False if opentelemetry not installed; True if installed
plugin._service_name    # "my-app"
```

---

## Test file: `test_plugin.py`

Location: `C:\Users\ok\Desktop\Package\test_plugin.py`

**Cost:** $0.00 — no API calls. Pure logic tests.

### Section overview

| # | What is tested | Checks |
|---|---|---|
| 1 | `Plugin` base class — default attrs, all default hook returns, custom subclass | 16 |
| 2 | Custom plugin with all 9 hooks — invocation + call tracking | 10 |
| 3 | `PluginLoader` — load/unload/get/all, fluent, duplicate, `__len__/__repr__` | 18 |
| 4 | `dispatch_on_request` — call order verification (3 plugins) | 2 |
| 5 | `dispatch_on_response` — chain modification, None passthrough | 2 |
| 6 | `dispatch_on_tool_call` — short-circuit, no-short-circuit | 3 |
| 7 | `dispatch_on_tool_result` — replacement chain, None passthrough | 2 |
| 8 | Session/error/security dispatchers — both plugins receive all 5 | 6 |
| 9 | `_safe_call` failure isolation — broken plugin doesn't crash | 2 |
| 10 | `PluginRegistry` — CRUD, duplicate, names sorted, `__len__/__contains__` | 18 |
| 11 | `LoggingPlugin` — construction, all hooks logged, include_content | 10 |
| 12 | `CostAlertPlugin` global mode — threshold, one-shot, accumulation | 11 |
| 13 | `CostAlertPlugin` per-session — independent sessions, one-shot each | 6 |
| 14 | `OpenTelemetryPlugin` — no-op when absent, all hooks callable | 6 |
| 15 | Pre-built pipeline — 3 plugins wired, full lifecycle dispatch | 8 |
| **Total** | | **120** |

---

### Section 1 -- Plugin base class

Verifies all default attribute values and hook return values without subclassing.

```python
p = Plugin()
assert p.name    == "unnamed_plugin"
assert p.version == "0.0.0"
assert "unnamed_plugin" in repr(p)

sentinel = object()
assert p.on_response(sentinel) is sentinel    # returns response unchanged
assert p.on_tool_call("tool", {}) is None     # returns None
assert p.on_tool_result("tool", "x") is None  # returns None
assert p.on_request([], "model") is None
```

---

### Section 2 -- Custom hook tracking

`_TrackingPlugin` appends `(hook_name, ...)` tuples to `self.calls` for every
invocation. All 9 hooks are called and verified.

```python
tracker = _TrackingPlugin()
tracker.on_request([{"role": "user", "content": "hi"}], "claude-haiku-4-5")
tracker.on_error(RuntimeError("boom"))
# ...
assert len(tracker.calls) == 9
assert ("on_error", "RuntimeError") in tracker.calls
```

---

### Section 3 -- PluginLoader management

Tests the full lifecycle: load, get, all, unload, duplicate replace.

```python
loader = PluginLoader()
ret = loader.load(p1)
assert ret is loader           # fluent

loader.load(p2)
assert loader.get("tracker") is p1
assert len(loader.all()) == 2
assert loader.all() is not loader._plugins   # copy

loader.unload("tracker")
assert loader.get("tracker") is None

loader.load(p2)  # p2 already loaded (name="debug") -> replaces
assert len(loader) == 1
```

---

### Section 4 -- dispatch_on_request call order

Three `_OrderPlugin` instances each append their ID to a shared list.

```python
call_order = []
dispatch_loader = PluginLoader().load(o1).load(o2).load(o3)
dispatch_loader.dispatch_on_request([...], "haiku")
assert call_order == [1, 2, 3]   # exact load order
```

---

### Section 5 -- dispatch_on_response chain

`_TransformPlugin` appends a suffix and returns the new string.
Three transforms chain: `"base" -> "base_A" -> "base_A_B" -> "base_A_B_C"`.

```python
result = t_loader.dispatch_on_response("base")
assert result == "base_A_B_C"

# Plugin returning None does NOT replace
pt_result = pt_loader.dispatch_on_response("unchanged")
assert pt_result == "unchanged"
```

---

### Section 6 -- dispatch_on_tool_call short-circuit

`_ShortCircuitPlugin` returns `"BLOCKED"` — the next plugin is never reached.

```python
sc_result = sc_loader.dispatch_on_tool_call("exec", {"cmd": "..."})
assert sc_result == "BLOCKED"
assert never_plugin.called is False    # not reached
```

---

### Section 7 -- dispatch_on_tool_result replacement

Two plugins each return a replacement; **last** non-None wins.

```python
tr = rp_loader.dispatch_on_tool_result("tool", "original")
assert tr == "second"   # p2's replacement overwrites p1's "first"
```

---

### Section 8 -- Session/error/security dispatchers

Two `_TrackingPlugin` instances are loaded. Five dispatchers are fired.
Both plugins receive all 5 calls (10 total invocations).

---

### Section 9 -- Failure isolation

`_BrokenPlugin.on_request` always raises `RuntimeError`.
`_HealthyPlugin.on_request` sets `self.called = True`.

```python
safe_loader = PluginLoader().load(_BrokenPlugin()).load(healthy)
safe_loader.dispatch_on_request([], "haiku")
assert healthy.called is True     # pipeline continued despite broken plugin

result = safe_loader._safe_call(_BrokenPlugin(), "on_request", [], "model")
assert result is None             # exception caught, None returned
```

---

### Section 10 -- PluginRegistry CRUD

Tests all methods including duplicate-replace behaviour.

```python
reg = PluginRegistry()
reg.register(pa); reg.register(pb); reg.register(pc)

assert reg.get("alpha") is pa
assert "alpha" in reg
assert "ghost" not in reg
assert reg.names() == sorted(reg.names())    # always sorted

pa2 = _DebugPlugin(); pa2.name = "alpha"
reg.register(pa2)
assert len(reg) == 3                # still 3
assert reg.get("alpha") is pa2     # replaced

reg.remove("gamma")
assert "gamma" not in reg
```

---

### Section 11 -- LoggingPlugin

Uses an in-memory `logging.Handler` to capture log records.
Verifies that each hook produces at least one log record.

```python
lp = LoggingPlugin(logger_instance=cap_logger, include_content=False)
lp.on_request([{"role": "user", "content": "test"}], "haiku")
# ...
assert any("Request" in r.getMessage() for r in log_records)
assert any(r.levelno == logging.ERROR for r in log_records)   # on_error -> ERROR

# include_content=True logs the message text
lp2 = LoggingPlugin(include_content=True)
lp2.on_request([{"role": "user", "content": "hello world"}], "haiku")
assert any("hello world" in r.getMessage() for r in records)
```

---

### Section 12 -- CostAlertPlugin global mode

```python
cap = CostAlertPlugin(threshold_usd=0.05, callback=lambda c,s: alerts.append((c,s)))

cap.on_session_cost_update("A", 0.02)   # _global_cost = 0.02, no alert
cap.on_session_cost_update("A", 0.04)   # _global_cost = 0.06 >= 0.05 -> alert!
cap.on_session_cost_update("A", 0.10)   # _alerted_global=True -> silent

assert len(alerts) == 1                    # one-shot
assert alerts[0][0] >= 0.05               # cumulative cost
assert cap._alerted_global is True
```

---

### Section 13 -- CostAlertPlugin per-session mode

Each session tracks independently and fires its own one-shot alert.

```python
psc = CostAlertPlugin(threshold_usd=0.03, callback=..., per_session=True)
psc.on_session_cost_update("A", 0.04)   # A alerts
psc.on_session_cost_update("B", 0.01)   # B below
psc.on_session_cost_update("B", 0.05)   # B alerts
psc.on_session_cost_update("A", 0.99)   # A already alerted, silent
psc.on_session_cost_update("C", 0.10)   # C alerts
assert len(sess_alerts) == 3            # A, B, C each once
```

---

### Section 14 -- OpenTelemetryPlugin no-op

Verifies the plugin constructs and all hooks are callable with no error
regardless of whether `opentelemetry` is installed.

```python
otp = OpenTelemetryPlugin(service_name="test-service")
assert otp._service_name == "test-service"
# If otel not installed: otp._otel_available is False, otp._tracer is None
otp.on_request([...], "haiku")    # no error
otp.on_tool_call("search", {})   # no error
otp.on_session_start("sess")     # no error
```

---

### Section 15 -- Pre-built pipeline

Three pre-built plugins wired together and a full lifecycle dispatched.

```python
pl = (
    PluginLoader()
    .load(LoggingPlugin(level="DEBUG"))
    .load(CostAlertPlugin(threshold_usd=0.01, callback=lambda c,s: alerts.append(c)))
    .load(OpenTelemetryPlugin())
)

pl.dispatch_on_session_start("sess", {"model": "haiku"})
pl.dispatch_on_request([...], "haiku")
final_resp = pl.dispatch_on_response(resp_obj)
pl.dispatch_on_session_cost_update("sess", 0.015)   # -> alert fires
pl.dispatch_on_session_end("sess")
pl.dispatch_on_error(RuntimeError("test"))

assert len(alerts) == 1                   # CostAlertPlugin fired
assert final_resp is not None             # LoggingPlugin passed response through
```

---

## Full test output

```
Plugin 'debug' is already loaded; replacing with new instance.
Plugin 'broken' raised an exception in on_request.
Replacing existing plugin 'alpha' in registry.
CostAlertPlugin: global cost exceeded $0.05 (current: $0.0600)
CostAlertPlugin: session sess-A exceeded $0.03 (current: $0.0400)
CostAlertPlugin: session sess-B exceeded $0.03 (current: $0.0500)
CostAlertPlugin: session sess-C exceeded $0.03 (current: $0.1000)
CostAlertPlugin: global cost exceeded $0.01 (current: $0.0150)
Error: RuntimeError: test pipeline error

---  1. Plugin -- base class, default hooks, repr  ---
  [PASS] default name
  [PASS] default version
  [PASS] repr contains name
  [PASS] repr contains version
  [PASS] on_response returns response
  [PASS] on_tool_call returns None
  [PASS] on_tool_result returns None
  [PASS] on_request returns None
  [PASS] on_session_start returns None
  [PASS] on_session_cost_update None
  [PASS] on_session_end returns None
  [PASS] on_error returns None
  [PASS] on_security_event returns None
  [PASS] custom name
  [PASS] custom version
  [PASS] custom repr

---  2. Plugin -- custom hook implementations and call tracking  ---
  [PASS] on_request recorded  ... (all 9 hooks)
  [PASS] total 9 hook calls

---  3. PluginLoader -- load/unload/get/all, __len__, __repr__  ---
  (18 checks all pass)

---  4-9. Dispatch methods, failure isolation  ---
  (13 checks all pass)

---  10. PluginRegistry  ---
  (18 checks all pass)

---  11-15. Pre-built plugins + pipeline  ---
  (31 checks all pass)

============================================================
  PASSED: 120  |  FAILED: 0
  ALL TESTS PASSED
============================================================
```

---

## Notes and gotchas

### 1. `_safe_call` only catches 4 exception types

```python
except (AttributeError, TypeError, ValueError, RuntimeError):
```

`KeyboardInterrupt`, `SystemExit`, `MemoryError`, and any exception not in
this list will propagate through. Design plugins to only raise these safe types,
or catch-all internally.

### 2. `dispatch_on_response` — None means "no change", not "clear"

If `on_response` returns `None`, the previous response is kept.
To intentionally return a "null" response, wrap it in a container object.

### 3. `dispatch_on_tool_call` short-circuits; `dispatch_on_tool_result` does not

- `on_tool_call`: returns first non-None value and stops calling remaining plugins
- `on_tool_result`: calls all plugins; each non-None return replaces the previous result

### 4. Duplicate `load()` replaces, not accumulates

```python
loader.load(MyPlugin())   # version 1
loader.load(MyPlugin())   # version 2 -- silently replaces v1 (WARNING log)
assert len(loader) == 1
```

`PluginRegistry.register()` has the same behaviour: duplicate `name` replaces
with a WARNING log, no exception raised.

### 5. `PluginRegistry` vs `PluginLoader`

| | `PluginRegistry` | `PluginLoader` |
|---|---|---|
| Purpose | Discovery / lookup | Active pipeline execution |
| Hooks fired | Never | Yes, on every dispatch call |
| Order | Insertion order | Load order |
| Duplicate | Replaces (warning) | Replaces (warning) |
| Remove | `remove("name")` raises `KeyError` | `unload("name")` raises `KeyError` |

### 6. `CostAlertPlugin` global mode accumulates **increments**, not snapshots

```python
# Global mode: adds each cost_usd to _global_cost
cap.on_session_cost_update("A", 0.02)   # _global_cost = 0.02
cap.on_session_cost_update("A", 0.04)   # _global_cost = 0.06 (not 0.04!)
```

Per-session mode uses the cost value **as given** (treats it as a snapshot,
not an increment) — it stores `_session_costs[session_name] = cost_usd`.

### 7. `OpenTelemetryPlugin` with otel installed

When `opentelemetry` is installed, the plugin creates real spans.
`_otel_available` is `True` and `_tracer` is set. The test skips the
`_otel_available is False` assertions when the package is present.

### 8. `on_error` in `LoggingPlugin` always logs at `ERROR` level

Even if `level="DEBUG"` is passed, `on_error` calls `self._logger.error(...)`.
All other hooks respect the configured level.

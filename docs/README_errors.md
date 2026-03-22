# claudekit · errors

Structured error hierarchy for the claudekit package. Every exception raised by claudekit is a subclass of `ClaudekitError`. Each instance carries a machine-readable error code, structured diagnostic context, a recovery hint, and the original upstream exception.

**Source files:** `_codes.py`, `_base.py`, `_rich.py`

---

## Architecture

```
ClaudekitError (root)
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
│   ├── MemoryKeyNotFoundError
│   └── MemoryValueTooLargeError
├── ToolInputValidationError
├── ToolJSONError
├── BatchError
│   ├── BatchNotReadyError
│   ├── BatchCancelledError
│   └── BatchPartialFailureError
├── SessionError
│   ├── SessionPausedError
│   ├── SessionTerminatedError
│   ├── SessionNameConflictError
│   └── SessionBudgetExceededError
├── PrecheckError
│   └── ContextWindowExceededError
├── OrchestratorError
├── ConfigurationError
│   ├── MissingAPIKeyError
│   ├── DeprecatedModelError
│   └── PlatformNotAvailableError
└── OverloadedError

Warnings (not exceptions):
├── ToolResultTooLargeWarning (UserWarning)
└── DeprecatedModelWarning (UserWarning)
```

---

## Error Codes (`_codes.py`)

Every `ClaudekitError` carries a `code` attribute set to one of these string constants. They are grouped by domain:

### Security

| Constant | Value | Used by |
|---|---|---|
| `PROMPT_INJECTION_DETECTED` | `"PROMPT_INJECTION_DETECTED"` | `PromptInjectionError` |
| `PII_DETECTED` | `"PII_DETECTED"` | `PIIDetectedError` |
| `JAILBREAK_DETECTED` | `"JAILBREAK_DETECTED"` | `JailbreakDetectedError` |
| `OUTPUT_VALIDATION_FAILED` | `"OUTPUT_VALIDATION_FAILED"` | `OutputValidationError` |
| `TOOL_BLOCKED` | `"TOOL_BLOCKED"` | `ToolBlockedError` |
| `PRICE_DISCLOSURE_DETECTED` | `"PRICE_DISCLOSURE_DETECTED"` | Security policies |

### Budget / Rate

| Constant | Value | Used by |
|---|---|---|
| `BUDGET_EXCEEDED` | `"BUDGET_EXCEEDED"` | `BudgetExceededError` |
| `RATE_LIMIT_EXCEEDED` | `"RATE_LIMIT_EXCEEDED"` | `RateLimitError` |
| `TOKEN_LIMIT_EXCEEDED` | `"TOKEN_LIMIT_EXCEEDED"` | `TokenLimitError` |

### Agent

| Constant | Value | Used by |
|---|---|---|
| `AGENT_TIMEOUT` | `"AGENT_TIMEOUT"` | `AgentTimeoutError` |
| `AGENT_MAX_TURNS` | `"AGENT_MAX_TURNS"` | `AgentMaxTurnsError` |
| `DELEGATION_LOOP` | `"DELEGATION_LOOP"` | `DelegationLoopError` |

### Memory

| Constant | Value | Used by |
|---|---|---|
| `MEMORY_BACKEND_ERROR` | `"MEMORY_BACKEND_ERROR"` | `MemoryBackendError` |
| `MEMORY_KEY_NOT_FOUND` | `"MEMORY_KEY_NOT_FOUND"` | `MemoryKeyNotFoundError` |
| `MEMORY_VALUE_TOO_LARGE` | `"MEMORY_VALUE_TOO_LARGE"` | `MemoryValueTooLargeError` |

### Tool

| Constant | Value | Used by |
|---|---|---|
| `TOOL_INPUT_VALIDATION_FAILED` | `"TOOL_INPUT_VALIDATION_FAILED"` | `ToolInputValidationError` |
| `TOOL_RESULT_TOO_LARGE` | `"TOOL_RESULT_TOO_LARGE"` | `ToolResultTooLargeWarning` |
| `TOOL_JSON_ERROR` | `"TOOL_JSON_ERROR"` | `ToolJSONError` |

### Batch

| Constant | Value | Used by |
|---|---|---|
| `BATCH_NOT_READY` | `"BATCH_NOT_READY"` | `BatchNotReadyError` |
| `BATCH_CANCELLED` | `"BATCH_CANCELLED"` | `BatchCancelledError` |
| `BATCH_PARTIAL_FAILURE` | `"BATCH_PARTIAL_FAILURE"` | `BatchPartialFailureError` |

### Session

| Constant | Value | Used by |
|---|---|---|
| `SESSION_PAUSED` | `"SESSION_PAUSED"` | `SessionPausedError` |
| `SESSION_TERMINATED` | `"SESSION_TERMINATED"` | `SessionTerminatedError` |
| `SESSION_NAME_CONFLICT` | `"SESSION_NAME_CONFLICT"` | `SessionNameConflictError` |
| `SESSION_BUDGET_EXCEEDED` | `"SESSION_BUDGET_EXCEEDED"` | `SessionBudgetExceededError` |

### Precheck

| Constant | Value | Used by |
|---|---|---|
| `CONTEXT_WINDOW_EXCEEDED` | `"CONTEXT_WINDOW_EXCEEDED"` | `ContextWindowExceededError` |

### Configuration

| Constant | Value | Used by |
|---|---|---|
| `MISSING_API_KEY` | `"MISSING_API_KEY"` | `MissingAPIKeyError` |
| `DEPRECATED_MODEL` | `"DEPRECATED_MODEL"` | `DeprecatedModelError` |
| `PLATFORM_NOT_AVAILABLE` | `"PLATFORM_NOT_AVAILABLE"` | `PlatformNotAvailableError` |
| `CONFIGURATION_ERROR` | `"CONFIGURATION_ERROR"` | `ConfigurationError` |

### SDK Wrapper

| Constant | Value | Used by |
|---|---|---|
| `OVERLOADED` | `"OVERLOADED"` | `OverloadedError` |
| `API_CONNECTION_ERROR` | `"API_CONNECTION_ERROR"` | `wrap_sdk_error` (APIConnectionError) |
| `API_TIMEOUT` | `"API_TIMEOUT"` | `wrap_sdk_error` (APITimeoutError) |

---

## Class: `ClaudekitError`

**Source:** `_base.py:54`
**Inherits:** `Exception`
**Role:** Root exception for all claudekit errors. Every other claudekit exception inherits from this.

### Constructor

```python
ClaudekitError(
    message: str = "",
    *,
    code: str = "",
    context: Optional[Dict[str, Any]] = None,
    recovery_hint: Optional[str] = None,
    original: Optional[BaseException] = None,
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `message` | `str` | `""` | Human-readable error description. Passed to `Exception.__init__()`. |
| `code` | `str` | `""` | Machine-readable error code constant from `_codes.py`. Keyword-only. |
| `context` | `Optional[Dict[str, Any]]` | `None` | Arbitrary key/value diagnostic data (e.g. `{"status_code": 429}`). Stored as `{}` if `None`. Keyword-only. |
| `recovery_hint` | `Optional[str]` | `None` | Suggestion for the caller on how to recover. Keyword-only. |
| `original` | `Optional[BaseException]` | `None` | The upstream exception that triggered this error. When set, also sets `self.__cause__` for exception chaining. Keyword-only. |

### Attributes

| Attribute | Type | Description |
|---|---|---|
| `message` | `str` | The human-readable error message. |
| `code` | `str` | Machine-readable error code. Empty string if not set. |
| `context` | `Dict[str, Any]` | Structured diagnostic data. Always a dict (never `None`). |
| `recovery_hint` | `Optional[str]` | Recovery suggestion or `None`. |
| `original` | `Optional[BaseException]` | Upstream exception or `None`. |
| `__cause__` | `Optional[BaseException]` | Set to `original` when `original` is not `None` (enables Python exception chaining). |

### Methods

#### `__repr__() -> str`

Returns a developer-oriented string like `ClaudekitError('message', code='CODE')`. The `code` part is omitted if the code is empty.

#### `__str__() -> str`

Returns a user-oriented string. Format: `"message [CODE] Hint: recovery_hint"`. The `[CODE]` part is omitted if code is empty. The `Hint:` part is omitted if `recovery_hint` is `None`.

### Usage

```python
from claudekit.errors import ClaudekitError

try:
    raise ClaudekitError(
        "Something went wrong",
        code="CUSTOM_ERROR",
        context={"request_id": "req_123"},
        recovery_hint="Try again later.",
    )
except ClaudekitError as e:
    print(e.code)           # "CUSTOM_ERROR"
    print(e.context)         # {"request_id": "req_123"}
    print(e.recovery_hint)   # "Try again later."
    print(e.original)        # None
    print(str(e))            # "Something went wrong [CUSTOM_ERROR] Hint: Try again later."
```

---

## Security Errors

All security errors inherit from `SecurityError`, which inherits from `ClaudekitError`.

### Class: `SecurityError`

**Source:** `_base.py:108`
**Inherits:** `ClaudekitError`
**Default message:** `"Security policy violation"`
**Default code:** `""` (empty)

Base class for all security-related errors. Has the same constructor signature as `ClaudekitError`.

---

### Class: `PromptInjectionError`

**Source:** `_base.py:129`
**Inherits:** `SecurityError`

Raised when a prompt-injection attempt is detected in user input.

| Parameter | Default |
|---|---|
| `message` | `"Prompt injection detected"` |
| `code` | `PROMPT_INJECTION_DETECTED` |
| `recovery_hint` | `"Sanitise or reject the offending input."` |

---

### Class: `PIIDetectedError`

**Source:** `_base.py:150`
**Inherits:** `SecurityError`

Raised when personally-identifiable information is found where it is prohibited.

| Parameter | Default |
|---|---|
| `message` | `"PII detected in content"` |
| `code` | `PII_DETECTED` |
| `recovery_hint` | `"Redact the PII before retrying."` |

---

### Class: `JailbreakDetectedError`

**Source:** `_base.py:171`
**Inherits:** `SecurityError`

Raised when a jailbreak attempt is detected.

| Parameter | Default |
|---|---|
| `message` | `"Jailbreak attempt detected"` |
| `code` | `JAILBREAK_DETECTED` |
| `recovery_hint` | `"Reject the offending input."` |

---

### Class: `OutputValidationError`

**Source:** `_base.py:192`
**Inherits:** `SecurityError`

Raised when model output fails a post-generation validation check.

| Parameter | Default |
|---|---|
| `message` | `"Output validation failed"` |
| `code` | `OUTPUT_VALIDATION_FAILED` |
| `recovery_hint` | `"Retry with tighter system-prompt constraints."` |

---

### Class: `ToolBlockedError`

**Source:** `_base.py:213`
**Inherits:** `SecurityError`

Raised when a tool invocation is blocked by a security policy.

| Parameter | Default |
|---|---|
| `message` | `"Tool invocation blocked by security policy"` |
| `code` | `TOOL_BLOCKED` |
| `recovery_hint` | `"Check the tool allow-list configuration."` |

---

## Budget / Rate Errors

All budget/rate errors inherit from `BudgetError`, which inherits from `ClaudekitError`.

### Class: `BudgetError`

**Source:** `_base.py:237`
**Inherits:** `ClaudekitError`
**Default message:** `"Budget constraint exceeded"`
**Default code:** `""` (empty)

Base class for budget and rate-related errors.

---

### Class: `BudgetExceededError`

**Source:** `_base.py:258`
**Inherits:** `BudgetError`

Raised when the configured spend budget has been exhausted.

| Parameter | Default |
|---|---|
| `message` | `"Budget exceeded"` |
| `code` | `BUDGET_EXCEEDED` |
| `recovery_hint` | `"Increase the budget or wait for a new billing period."` |

---

### Class: `RateLimitError`

**Source:** `_base.py:279`
**Inherits:** `BudgetError`

Raised when the API rate limit has been reached. Typically corresponds to HTTP 429 from the Anthropic API.

| Parameter | Default |
|---|---|
| `message` | `"Rate limit exceeded"` |
| `code` | `RATE_LIMIT_EXCEEDED` |
| `recovery_hint` | `"Back off and retry after the indicated delay."` |

---

### Class: `TokenLimitError`

**Source:** `_base.py:300`
**Inherits:** `BudgetError`

Raised when a per-request or per-session token limit is exceeded.

| Parameter | Default |
|---|---|
| `message` | `"Token limit exceeded"` |
| `code` | `TOKEN_LIMIT_EXCEEDED` |
| `recovery_hint` | `"Reduce the input size or raise the token cap."` |

---

## Agent Errors

All agent errors inherit from `AgentError`, which inherits from `ClaudekitError`.

### Class: `AgentError`

**Source:** `_base.py:324`
**Inherits:** `ClaudekitError`
**Default message:** `"Agent error"`
**Default code:** `""` (empty)

Base class for all agent-related errors.

---

### Class: `AgentTimeoutError`

**Source:** `_base.py:345`
**Inherits:** `AgentError`

Raised when the agent run exceeds its wall-clock timeout.

| Parameter | Default |
|---|---|
| `message` | `"Agent timed out"` |
| `code` | `AGENT_TIMEOUT` |
| `recovery_hint` | `"Increase the timeout or simplify the task."` |

---

### Class: `AgentMaxTurnsError`

**Source:** `_base.py:366`
**Inherits:** `AgentError`

Raised when the agent has exhausted its maximum number of turns.

| Parameter | Default |
|---|---|
| `message` | `"Agent reached maximum turns"` |
| `code` | `AGENT_MAX_TURNS` |
| `recovery_hint` | `"Increase max_turns or break the task into sub-tasks."` |

---

### Class: `DelegationLoopError`

**Source:** `_base.py:387`
**Inherits:** `AgentError`

Raised when a delegation cycle is detected between sub-agents.

| Parameter | Default |
|---|---|
| `message` | `"Delegation loop detected"` |
| `code` | `DELEGATION_LOOP` |
| `recovery_hint` | `"Review delegation rules to break the cycle."` |

---

## Memory Errors

All memory errors inherit from `ClaudekitMemoryError`, which inherits from `ClaudekitError`. Named `ClaudekitMemoryError` (not `MemoryError`) to avoid shadowing the built-in Python `MemoryError`.

### Class: `ClaudekitMemoryError`

**Source:** `_base.py:411`
**Inherits:** `ClaudekitError`
**Default message:** `"Memory subsystem error"`
**Default code:** `""` (empty)

---

### Class: `MemoryBackendError`

**Source:** `_base.py:436`
**Inherits:** `ClaudekitMemoryError`

Raised when the memory backend (e.g. SQLite, JSON) is unreachable or returns an error.

| Parameter | Default |
|---|---|
| `message` | `"Memory backend error"` |
| `code` | `MEMORY_BACKEND_ERROR` |
| `recovery_hint` | `"Check the memory backend connection settings."` |

---

### Class: `MemoryKeyNotFoundError`

**Source:** `_base.py:457`
**Inherits:** `ClaudekitMemoryError`

Raised when the requested key does not exist in the memory store.

| Parameter | Default |
|---|---|
| `message` | `"Memory key not found"` |
| `code` | `MEMORY_KEY_NOT_FOUND` |
| `recovery_hint` | `"Verify the key name or populate it before reading."` |

---

### Class: `MemoryValueTooLargeError`

**Source:** `_base.py:478`
**Inherits:** `ClaudekitMemoryError`

Raised when the value exceeds the configured maximum size for memory entries.

| Parameter | Default |
|---|---|
| `message` | `"Memory value too large"` |
| `code` | `MEMORY_VALUE_TOO_LARGE` |
| `recovery_hint` | `"Reduce the value size or increase the limit."` |

---

## Tool Errors

### Class: `ToolInputValidationError`

**Source:** `_base.py:502`
**Inherits:** `ClaudekitError` (not grouped under a parent)

Raised when the model-supplied input for a tool fails schema validation.

| Parameter | Default |
|---|---|
| `message` | `"Tool input validation failed"` |
| `code` | `TOOL_INPUT_VALIDATION_FAILED` |
| `recovery_hint` | `"Check the tool schema and retry."` |

---

### Class: `ToolJSONError`

**Source:** `_base.py:531`
**Inherits:** `ClaudekitError`

Raised when a tool returns non-JSON or malformed JSON when JSON was expected.

| Parameter | Default |
|---|---|
| `message` | `"Tool JSON error"` |
| `code` | `TOOL_JSON_ERROR` |
| `recovery_hint` | `"Ensure the tool returns valid JSON."` |

---

### Warning: `ToolResultTooLargeWarning`

**Source:** `_base.py:523`
**Inherits:** `UserWarning`

This is a **warning**, not an exception. Emitted when a tool result is larger than recommended. Can be filtered with the `warnings` module:

```python
import warnings
from claudekit.errors import ToolResultTooLargeWarning
warnings.filterwarnings("ignore", category=ToolResultTooLargeWarning)
```

---

## Batch Errors

All batch errors inherit from `BatchError`, which inherits from `ClaudekitError`.

### Class: `BatchError`

**Source:** `_base.py:555`
**Inherits:** `ClaudekitError`
**Default message:** `"Batch error"`
**Default code:** `""` (empty)

---

### Class: `BatchNotReadyError`

**Source:** `_base.py:576`
**Inherits:** `BatchError`

Raised when the batch result is requested before processing completed.

| Parameter | Default |
|---|---|
| `message` | `"Batch not ready"` |
| `code` | `BATCH_NOT_READY` |
| `recovery_hint` | `"Poll the batch status or use an async callback."` |

---

### Class: `BatchCancelledError`

**Source:** `_base.py:597`
**Inherits:** `BatchError`

Raised when the batch was cancelled before it completed.

| Parameter | Default |
|---|---|
| `message` | `"Batch cancelled"` |
| `code` | `BATCH_CANCELLED` |
| `recovery_hint` | `"Re-submit the batch if cancellation was unintended."` |

---

### Class: `BatchPartialFailureError`

**Source:** `_base.py:618`
**Inherits:** `BatchError`

Raised when some items in the batch failed while others succeeded.

| Parameter | Default |
|---|---|
| `message` | `"Batch partial failure"` |
| `code` | `BATCH_PARTIAL_FAILURE` |
| `recovery_hint` | `"Inspect context['failed_items'] and retry them."` |

---

## Session Errors

All session errors inherit from `SessionError`, which inherits from `ClaudekitError`.

### Class: `SessionError`

**Source:** `_base.py:642`
**Inherits:** `ClaudekitError`
**Default message:** `"Session error"`
**Default code:** `""` (empty)

---

### Class: `SessionPausedError`

**Source:** `_base.py:663`
**Inherits:** `SessionError`

Raised when an operation is attempted on a paused session.

| Parameter | Default |
|---|---|
| `message` | `"Session is paused"` |
| `code` | `SESSION_PAUSED` |
| `recovery_hint` | `"Resume the session before performing operations."` |

---

### Class: `SessionTerminatedError`

**Source:** `_base.py:684`
**Inherits:** `SessionError`

Raised when an operation is attempted on a terminated session.

| Parameter | Default |
|---|---|
| `message` | `"Session is terminated"` |
| `code` | `SESSION_TERMINATED` |
| `recovery_hint` | `"Create a new session."` |

---

### Class: `SessionNameConflictError`

**Source:** `_base.py:705`
**Inherits:** `SessionError`

Raised when a session with the same name already exists.

| Parameter | Default |
|---|---|
| `message` | `"Session name conflict"` |
| `code` | `SESSION_NAME_CONFLICT` |
| `recovery_hint` | `"Use a unique session name or resume the existing one."` |

---

### Class: `SessionBudgetExceededError`

**Source:** `_base.py:726`
**Inherits:** `SessionError`

Raised when the per-session budget has been exhausted.

| Parameter | Default |
|---|---|
| `message` | `"Session budget exceeded"` |
| `code` | `SESSION_BUDGET_EXCEEDED` |
| `recovery_hint` | `"Increase the session budget or start a new session."` |

---

## Precheck Errors

### Class: `PrecheckError`

**Source:** `_base.py:750`
**Inherits:** `ClaudekitError`
**Default message:** `"Precheck failed"`
**Default code:** `""` (empty)

Base class for pre-flight check errors.

---

### Class: `ContextWindowExceededError`

**Source:** `_base.py:771`
**Inherits:** `PrecheckError`

Raised when the estimated token count exceeds the model's context window.

| Parameter | Default |
|---|---|
| `message` | `"Context window exceeded"` |
| `code` | `CONTEXT_WINDOW_EXCEEDED` |
| `recovery_hint` | `"Reduce the input size or use a model with a larger context window."` |

---

## Orchestrator Errors

### Class: `OrchestratorError`

**Source:** `_base.py:795`
**Inherits:** `ClaudekitError`
**Default message:** `"Orchestrator error"`
**Default code:** `""` (empty)

Raised when an error originates from the orchestration layer.

---

## Configuration Errors

All configuration errors inherit from `ConfigurationError`, which inherits from `ClaudekitError`.

### Class: `ConfigurationError`

**Source:** `_base.py:819`
**Inherits:** `ClaudekitError`
**Default message:** `"Configuration error"`
**Default code:** `CONFIGURATION_ERROR`

Base class for configuration and environment problems.

---

### Class: `MissingAPIKeyError`

**Source:** `_base.py:840`
**Inherits:** `ConfigurationError`

Raised when no API key is provided or the key is invalid.

| Parameter | Default |
|---|---|
| `message` | `"Missing or invalid API key"` |
| `code` | `MISSING_API_KEY` |
| `recovery_hint` | `"Set the ANTHROPIC_API_KEY environment variable or pass api_key explicitly."` |

---

### Class: `DeprecatedModelError`

**Source:** `_base.py:861`
**Inherits:** `ConfigurationError`

Raised when the requested model has been deprecated and is no longer available.

| Parameter | Default |
|---|---|
| `message` | `"Model is deprecated"` |
| `code` | `DEPRECATED_MODEL` |
| `recovery_hint` | `"Switch to a supported model."` |

---

### Class: `PlatformNotAvailableError`

**Source:** `_base.py:882`
**Inherits:** `ConfigurationError`

Raised when the requested platform or feature is not available.

| Parameter | Default |
|---|---|
| `message` | `"Platform not available"` |
| `code` | `PLATFORM_NOT_AVAILABLE` |
| `recovery_hint` | `"Check platform requirements and supported environments."` |

---

## SDK Wrapper Errors

### Class: `OverloadedError`

**Source:** `_base.py:906`
**Inherits:** `ClaudekitError`

Raised when the Anthropic API is temporarily overloaded (HTTP 529).

| Parameter | Default |
|---|---|
| `message` | `"API is overloaded"` |
| `code` | `OVERLOADED` |
| `recovery_hint` | `"Retry with exponential back-off."` |

---

## Warning: `DeprecatedModelWarning`

**Source:** `_rich.py:45`
**Inherits:** `UserWarning`

Warning emitted when a deprecated (but still functional) model is used. This is a `UserWarning`, not an exception. It can be silenced:

```python
import warnings
from claudekit.errors import DeprecatedModelWarning
warnings.filterwarnings("ignore", category=DeprecatedModelWarning)
```

---

## Function: `wrap_sdk_error`

**Source:** `_rich.py:323`

```python
def wrap_sdk_error(exc: BaseException) -> ClaudekitError
```

Programmatically wraps an Anthropic SDK exception into the corresponding claudekit error. Use inside `try`/`except` blocks to convert caught SDK errors on demand.

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `exc` | `BaseException` | The Anthropic SDK exception to wrap. |

**Returns:** `ClaudekitError` — the wrapped exception with structured `code`, `context`, and `recovery_hint`.

**Behavior:** If the exception is not a recognised Anthropic type, returns a generic `ClaudekitError` with the message and any context that can be extracted.

### SDK Exception Mapping

The internal `_wrap_sdk_exception` function maps SDK exceptions in this order (order matters because of inheritance):

| SDK Exception | HTTP | Maps to | Code |
|---|---|---|---|
| `anthropic.APIConnectionError` | — | `ConfigurationError` | `API_CONNECTION_ERROR` |
| `anthropic.APITimeoutError` | — | `AgentTimeoutError` | `API_TIMEOUT` |
| `anthropic.AuthenticationError` | 401 | `MissingAPIKeyError` | `MISSING_API_KEY` |
| `anthropic.PermissionDeniedError` | 403 | `ConfigurationError` | `API_CONNECTION_ERROR` |
| `anthropic.RateLimitError` | 429 | `RateLimitError` | `RATE_LIMIT_EXCEEDED` |
| `anthropic.RequestTooLargeError` | 413 | `ContextWindowExceededError` | `CONTEXT_WINDOW_EXCEEDED` |
| `anthropic.OverloadedError` | 529 | `OverloadedError` | `OVERLOADED` |
| `anthropic.ServiceUnavailableError` | 503 | `ClaudekitError` | `API_CONNECTION_ERROR` |
| `anthropic.InternalServerError` | 500+ | `ClaudekitError` | `API_CONNECTION_ERROR` |
| `anthropic.UnprocessableEntityError` | 422 | `ClaudekitError` | `"UNPROCESSABLE_ENTITY"` |
| `anthropic.ConflictError` | 409 | `ClaudekitError` | `"CONFLICT"` |
| `anthropic.NotFoundError` | 404 | `ClaudekitError` | `"NOT_FOUND"` |
| `anthropic.BadRequestError` | 400 | `ClaudekitError` | `"BAD_REQUEST"` |
| `anthropic.APIError` (catch-all) | any | `ClaudekitError` | `""` |

### Context Extraction

For every wrapped error, the following fields are extracted and placed into `context`:

| Key | Source | Description |
|---|---|---|
| `status_code` | `exc.status_code` or `exc.response.status_code` | HTTP status code |
| `request_id` | `exc.response.headers["x-request-id"]` | Anthropic request identifier |
| `body` | `exc.body` | Raw response body |

### Usage

```python
import anthropic
from claudekit.errors import wrap_sdk_error, MissingAPIKeyError

try:
    client.messages.create(...)
except anthropic.AuthenticationError as exc:
    wrapped = wrap_sdk_error(exc)
    assert isinstance(wrapped, MissingAPIKeyError)
    print(wrapped.code)           # "MISSING_API_KEY"
    print(wrapped.recovery_hint)  # "Set the ANTHROPIC_API_KEY..."
    print(wrapped.context)        # {"status_code": 401, "request_id": "..."}
    raise wrapped from exc
```

---

## Function: `enable_rich_errors`

**Source:** `_rich.py:298`

```python
def enable_rich_errors() -> None
```

Patches `sys.excepthook` to automatically wrap unhandled Anthropic SDK exceptions in claudekit errors before displaying them. The original hook is saved on the first call and restored as the fallback.

**Behavior:**
- Calling this function more than once is safe — the original hook is only saved on the first invocation.
- If `sys.excepthook` is already `_rich_excepthook`, the function returns immediately (no-op).
- When an unhandled exception is raised:
  1. If it is a recognised Anthropic SDK exception → wrapped via `_wrap_sdk_exception` → displayed using the original hook
  2. Otherwise → the original hook is called unchanged

**Usage:**

```python
from claudekit.errors import enable_rich_errors
enable_rich_errors()

# From this point, any unhandled anthropic.RateLimitError
# will surface as claudekit.errors.RateLimitError with structured context.
```

---

## Internal Helper Functions (`_rich.py`)

These are not exported but are used by `wrap_sdk_error` and `enable_rich_errors`:

### `_extract_request_id(exc: BaseException) -> Optional[str]`

Tries to pull the `x-request-id` header from the SDK error's response. Falls back to `request-id` header. Returns `None` if not available.

### `_extract_status_code(exc: BaseException) -> Optional[int]`

Tries to pull the HTTP status code from `exc.status_code` or `exc.response.status_code`. Returns `None` if not available.

### `_build_context(exc: BaseException) -> Dict[str, Any]`

Builds a diagnostic context dict from an SDK exception. Includes `status_code`, `request_id`, and `body` when available.

### `_wrap_sdk_exception(exc: BaseException) -> Optional[ClaudekitError]`

Core mapping function. Returns `None` if the exception is not a recognised Anthropic SDK type. Requires `anthropic` as a lazy import — returns `None` if `anthropic` is not installed.

### `_rich_excepthook(exc_type, exc_value, exc_tb) -> None`

Custom `sys.excepthook` installed by `enable_rich_errors()`. Wraps recognised SDK exceptions and delegates to the original hook for display.

---

## Module Exports (`__all__`)

The `__init__.py` re-exports everything from all three submodules. Total: **69 names**.

- **31 error codes** (string constants)
- **35 exception classes** (including base classes)
- **1 warning class** (`DeprecatedModelWarning` from `_rich.py`)
- **2 utility functions** (`enable_rich_errors`, `wrap_sdk_error`)

---

## Edge Cases & Gotchas

1. **All constructor parameters except `message` are keyword-only** (enforced by `*` in the signature). You cannot pass `code` or `context` positionally.

2. **`context` is never `None`** on a constructed instance — it defaults to `{}` in the constructor. You can always safely access `e.context["key"]` without checking for `None`.

3. **`ToolResultTooLargeWarning` and `DeprecatedModelWarning` are `UserWarning` subclasses**, not exceptions. They cannot be caught with `except` — use `warnings.catch_warnings()` or `warnings.filterwarnings()` instead.

4. **`ClaudekitMemoryError` is named to avoid shadowing Python's built-in `MemoryError`**. If you import `from claudekit.errors import *`, you will not shadow the built-in.

5. **`wrap_sdk_error` checks order matters**: `OverloadedError` is checked before `InternalServerError` because the Anthropic SDK's `OverloadedError` inherits from `InternalServerError`. If checked in reverse order, overloaded errors would be mapped to the wrong claudekit error.

6. **`enable_rich_errors` is global and idempotent**: it modifies `sys.excepthook` globally. Safe to call multiple times. There is no `disable_rich_errors()` function — once installed, it stays active for the process lifetime.

7. **`original` sets `__cause__`**: When you pass `original=exc`, Python's exception chaining is automatically enabled. The traceback will show `"The above exception was the direct cause of the following exception"`.

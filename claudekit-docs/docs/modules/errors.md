---
title: Errors
description: Full error hierarchy rooted at ClaudekitError. Every exception carries message, code, context dict, and recovery_hint.
module: claudekit.errors
classes: [ClaudekitError]
---

# Errors

Every exception raised by claudekit is a subclass of `ClaudekitError`. All errors carry structured metadata for programmatic handling.

## ClaudekitError

```python
from claudekit.errors import ClaudekitError

try:
    # any claudekit operation
except ClaudekitError as e:
    print(e.message)          # str — human-readable description
    print(e.code)             # str — machine-readable constant (e.g. "PROMPT_INJECTION_DETECTED")
    print(e.context)          # dict — structured diagnostic data
    print(e.recovery_hint)    # str | None — suggestion for the caller
    print(e.original)         # Exception | None — upstream exception if any
```

---

## Error hierarchy

```
ClaudekitError
├── SecurityError
│   ├── PromptInjectionError      code: PROMPT_INJECTION_DETECTED
│   ├── PIIDetectedError          code: PII_DETECTED
│   ├── JailbreakDetectedError    code: JAILBREAK_DETECTED
│   ├── OutputValidationError     code: OUTPUT_VALIDATION_FAILED
│   └── ToolBlockedError          code: TOOL_BLOCKED
├── BudgetError
│   ├── BudgetExceededError       code: BUDGET_EXCEEDED
│   ├── RateLimitError            code: RATE_LIMIT_EXCEEDED
│   └── TokenLimitError           code: TOKEN_LIMIT_EXCEEDED
├── AgentError
│   ├── AgentTimeoutError         code: AGENT_TIMEOUT
│   ├── AgentMaxTurnsError        code: AGENT_MAX_TURNS
│   └── DelegationLoopError       code: DELEGATION_LOOP
├── ClaudekitMemoryError
│   ├── MemoryBackendError        code: MEMORY_BACKEND_ERROR
│   └── MemoryValueTooLargeError  code: MEMORY_VALUE_TOO_LARGE
├── SessionError
│   ├── SessionPausedError        code: SESSION_PAUSED
│   ├── SessionTerminatedError    code: SESSION_TERMINATED
│   ├── SessionNameConflictError  code: SESSION_NAME_CONFLICT
│   └── SessionBudgetExceededError code: SESSION_BUDGET_EXCEEDED
├── BatchError
│   ├── BatchNotReadyError        code: BATCH_NOT_READY
│   ├── BatchCancelledError       code: BATCH_CANCELLED
│   └── BatchPartialFailureError  code: BATCH_PARTIAL_FAILURE
├── ConfigurationError            code: CONFIGURATION_ERROR
│   ├── MissingAPIKeyError        code: MISSING_API_KEY
│   └── DeprecatedModelError      code: DEPRECATED_MODEL
└── OrchestratorError
    (wraps DelegationLoopError and routing failures)
```

---

## Importing exceptions

```python
from claudekit.errors import (
    ClaudekitError,
    # Security
    SecurityError,
    PromptInjectionError,
    PIIDetectedError,
    JailbreakDetectedError,
    OutputValidationError,
    ToolBlockedError,
    # Budget
    BudgetError,
    BudgetExceededError,
    RateLimitError,
    TokenLimitError,
    # Agents
    AgentError,
    AgentTimeoutError,
    AgentMaxTurnsError,
    DelegationLoopError,
    # Memory
    ClaudekitMemoryError,
    MemoryBackendError,
    MemoryValueTooLargeError,
    # Sessions
    SessionError,
    SessionPausedError,
    SessionTerminatedError,
    SessionNameConflictError,
    SessionBudgetExceededError,
    # Batches
    BatchError,
    BatchNotReadyError,
    BatchCancelledError,
    BatchPartialFailureError,
    # Configuration
    ConfigurationError,
    MissingAPIKeyError,
    DeprecatedModelError,
    # Orchestration
    OrchestratorError,
)
```

---

## Error handling patterns

### Catch by category

```python
from claudekit.errors import SecurityError, BudgetError

try:
    response = client.messages.create(...)
except SecurityError as e:
    log.warning("Security block: %s [%s]", e.message, e.code)
    return {"error": "Request blocked", "code": e.code}
except BudgetError as e:
    log.error("Budget exceeded: %s", e.context)
    raise
```

### Catch specific error

```python
from claudekit.errors import PromptInjectionError, RateLimitError
import time

try:
    layer.check_request(messages, model="claude-haiku-4-5")
except PromptInjectionError as e:
    return {"blocked": True, "user_id": e.context.get("user_id")}
except RateLimitError as e:
    retry_after = e.context.get("retry_after_seconds", 60)
    time.sleep(retry_after)
    # retry...
```

### Use recovery_hint

```python
from claudekit.errors import ClaudekitError

try:
    mem.save("key", huge_value)
except ClaudekitError as e:
    print(e.message)
    if e.recovery_hint:
        print("Hint:", e.recovery_hint)
```

---

## DeprecatedModelWarning

Not an exception — a Python `Warning` subclass emitted by `TrackedClient` when a deprecated model is used.

```python
import warnings
from claudekit.errors import DeprecatedModelWarning

with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    client.messages.create(model="claude-3-haiku-20240307", ...)
    if w and issubclass(w[0].category, DeprecatedModelWarning):
        print(w[0].message)
        # "Model 'claude-3-haiku-20240307' is deprecated (EOL 2026-04-20)."
```

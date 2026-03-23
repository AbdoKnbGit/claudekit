# Security

**Module:** `claudekit.security` · **Classes:** `SecurityLayer`, `Policy`, `InputSanitizerPolicy`, `PromptInjectionPolicy`, `JailbreakPolicy`, `PIIPolicy`, `OutputSchemaPolicy`, `RateLimitPolicy`, `BudgetCapPolicy`, `ToolGuardPolicy`

`claudekit.security` provides a composable policy pipeline applied to every Claude API call. Policies run in order on the request before it is sent, and on the response before it is returned to the caller.

## SecurityLayer

```python
from claudekit.security import SecurityLayer
from claudekit.security.policies import InputSanitizerPolicy, RateLimitPolicy

layer = SecurityLayer([
    InputSanitizerPolicy(),
    RateLimitPolicy(requests_per_minute=60),
])

# Attach to client — applied automatically on every call
from claudekit import TrackedClient
client = TrackedClient(security=layer)

# Or call manually
layer.check_request(messages, model="claude-haiku-4-5", user_id="user-42")

# Or pass a SecurityContext for richer per-request metadata
from claudekit.security import SecurityContext
ctx = SecurityContext(user_id="user:123", session_id="sess:456")
layer.check_request(messages, model="claude-haiku-4-5", metadata=ctx.__dict__)
response = layer.check_response(response, model="claude-haiku-4-5")
```

### check_request

```python
layer.check_request(
    messages: list[dict],       # message list for the API call
    model: str = "",            # model ID
    user_id: str | None = None, # caller-supplied user identifier
    metadata: dict | None = None,
    trusted_caller: bool = False,   # skip injection/jailbreak checks
)
# Raises a SecurityError subclass if any policy blocks the request.
```

### check_response

```python
response = layer.check_response(
    response: Any,              # raw API response
    model: str = "",
    user_id: str | None = None,
    metadata: dict | None = None,
)
# Returns the (possibly modified) response.
# Policies may redact PII or transform the response.
```

### Policy management

```python
layer.add_policy(policy)               # append
layer.remove_policy("policy-name")     # remove by name (raises KeyError if missing)
layer.replace_policy("old-name", new)  # replace by name
layer.policies                         # list[Policy] — read-only copy
```

---

## Built-in Policies

### InputSanitizerPolicy

Strips or escapes dangerous patterns from all user messages before they reach the model.

```python
from claudekit.security.policies import InputSanitizerPolicy

policy = InputSanitizerPolicy(
    strip_html=True,           # strip HTML tags
    strip_scripts=True,        # strip <script> blocks
    max_length=10_000,         # truncate inputs exceeding this
)
```

### PromptInjectionPolicy  (alias: `Policy.no_prompt_injection()`)

Detects prompt-injection patterns using heuristics.

```python
from claudekit.security.policies import PromptInjectionPolicy

policy = PromptInjectionPolicy(
    sensitivity="high",        # "low" | "medium" | "high"
    action="block",            # "block" | "warn"
)
# Raises PromptInjectionError on detection.
```

### JailbreakPolicy  (alias: `Policy.no_jailbreak()`)

Detects jailbreak attempts (role-play escalation, system prompt override, DAN, etc.).

```python
from claudekit.security.policies import JailbreakPolicy

policy = JailbreakPolicy(sensitivity="medium", action="block")
# Raises JailbreakDetectedError on detection.
```

### PIIPolicy  (alias: `Policy.no_pii_in_output()`)

Scans model responses for PII (emails, phone numbers, SSNs, credit cards) and either redacts or blocks.

```python
from claudekit.security.policies import PIIPolicy

policy = PIIPolicy(action="redact")   # "redact" | "block"
# On "redact": replaces PII with [REDACTED].
# On "block": raises PIIDetectedError.
```

### OutputSchemaPolicy  (alias: `Policy.output_schema()`)

Validates that model output matches an expected JSON schema.

```python
from claudekit.security.policies import OutputSchemaPolicy

policy = OutputSchemaPolicy(
    schema={"type": "object", "required": ["findings", "risk_score"]},
)
# Raises OutputValidationError if the response is not valid JSON or doesn't match.
```

### RateLimitPolicy  (alias: `Policy.rate_limit()`)

Tracks requests per minute per user_id (or globally) and blocks when exceeded.

```python
from claudekit.security.policies import RateLimitPolicy

policy = RateLimitPolicy(
    requests_per_minute=60,
    per_user=True,       # track per user_id; False = global
    action="block",      # "block" | "warn"
)
# Raises RateLimitError when exceeded.
```

### BudgetCapPolicy  (alias: `Policy.budget_cap()` / `Policy.max_cost_per_user()`)

Blocks calls after a cumulative cost threshold is exceeded.

```python
from claudekit.security.policies import BudgetCapPolicy

policy = BudgetCapPolicy(max_cost_usd=10.0, per_user=False)
# Raises BudgetExceededError when threshold is crossed.

# Alternative: per-user sliding-window budget
policy = Policy.max_cost_per_user(limit_usd=1.00, window="24h")
```

### ToolGuardPolicy  (alias: `Policy.tool_guard()`)

Blocks specific tool invocations matching glob patterns.

```python
from claudekit.security.policies import ToolGuardPolicy

policy = ToolGuardPolicy(
    rules={
        "shell_exec": ["*rm -rf*", "*format*"],   # glob patterns
        "file_write": ["*/etc/*", "*/root/*"],
    },
    action="block",   # "block" | "warn"
)
# Raises ToolBlockedError when a matched tool call is attempted.
```

---

## Policy Factory

All policies are available via `Policy` factory methods:

```python
from claudekit.security import Policy

Policy.no_prompt_injection(sensitivity="high")
Policy.no_jailbreak(sensitivity="medium")
Policy.no_pii_in_output(action="redact")
Policy.output_schema(schema={...})
Policy.rate_limit(requests_per_minute=60)
Policy.budget_cap(max_cost_usd=10.0)
Policy.tool_guard(rules={"shell": ["*rm*"]})
```

---

## Presets

One-liner security configurations for common deployment scenarios:

```python
from claudekit.security.presets import (
    DeveloperToolsPreset,
    CustomerFacingPreset,
    FinancialServicesPreset,
    HealthcarePreset,
    InternalToolsPreset,
)

layer = DeveloperToolsPreset()     # injection + jailbreak + rate_limit(120/min)
layer = CustomerFacingPreset()     # sanitizer + injection + jailbreak + PII redaction + rate_limit(30/min)
layer = FinancialServicesPreset()  # all policies + strict budget cap + PII block
layer = HealthcarePreset()         # PII block + injection + output schema validation
layer = InternalToolsPreset()      # injection + rate_limit(300/min) + tool_guard
```

Each preset returns a `SecurityLayer` instance and can be further customised:

```python
layer = CustomerFacingPreset()
layer.add_policy(Policy.budget_cap(max_cost_usd=5.0))
```

---

## Writing a Custom Policy

```python
from claudekit.security._policy import Policy
from claudekit.security._context import SecurityContext

class NoSwearWordsPolicy(Policy):
    name = "no_swear_words"

    def check_request(self, messages: list[dict], ctx: SecurityContext) -> None:
        for msg in messages:
            content = str(msg.get("content", ""))
            if "badword" in content.lower():
                from claudekit.errors import SecurityError
                raise SecurityError("Inappropriate language detected",
                                    code="INAPPROPRIATE_CONTENT",
                                    context={"user_id": ctx.user_id})

    def check_response(self, response: Any, ctx: SecurityContext) -> Any:
        return response   # no response-side check needed
```

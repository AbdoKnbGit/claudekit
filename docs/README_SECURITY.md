# claudekit · security

Composable security policy framework for Anthropic Claude. Intercept, scan, and block requests or responses based on safety, budget, and compliance rules.

**Source files:** `_layer.py`, `_context.py`, `_policy.py`, `policies/*`, `presets/*`

---

## Core Architecture

### `SecurityLayer`
**Source:** `_layer.py:19`
The central orchestrator for the security pipeline. It holds an ordered list of policies and executes them sequentially.

- **`check_request(messages, model, user_id, ...)`**: Runs all policies on outgoing messages. Raises `SecurityError` if any policy blocks.
- **`check_response(response, model, user_id, ...)`**: Runs all policies on incoming responses. Can mutate the response (e.g., for redaction).

### `SecurityContext`
**Source:** `_context.py:17`
A dataclass carrying request metadata (`user_id`, `request_id`, `model`, `timestamp`, `metadata`, `trusted_caller`). A new context is created for every check.

### `Policy` (Base Class)
**Source:** `_policy.py:32`
The abstract base class for all policies.
- **`check_request(messages, context)`**: Override to inspect outbound data.
- **`check_response(response, context)`**: Override to inspect or modify inbound data.

---

## Concrete Policies

| Policy | Description | Key Features |
|---|---|---|
| **`BudgetPolicy`** | Enforces USD/token caps. | Per-user tracking, windows (1m to 30d), warning callbacks, pluggable backends (Redis ready). |
| **`PromptInjectionPolicy`** | Detects adversarial prompts. | 3 sensitivity levels, handles RTL injection, base64 payloads, and tool-result injections. |
| **`JailbreakPolicy`** | LLM-based classification. | Uses a fast model (e.g., Haiku) to classify intent. Result caching included. |
| **`PIIPolicy`** | Scans for sensitive data. | 11 types (SSN, CC, Email, etc.), Luhn validation for cards, auto-redaction support. |
| **`RateLimitPolicy`** | Sliding-window throttling. | Per-minute/hour/day limits, in-memory or Redis-compatible backends. |
| **`OutputSchemaPolicy`** | Structural validation. | Validates response against Pydantic models with auto-retries and markdown-fence stripping. |
| **`InputSanitizerPolicy`** | Pre-processing cleanup. | Strips HTML, escapes XML, truncates oversized tool results. |
| **`ToolGuardPolicy`** | Input validation for tools. | Blocks dangerous tool inputs (e.g., `rm -rf`, `DROP TABLE`) via glob or regex. |

---

## Security Presets

Presets are pre-configured `SecurityLayer` subclasses tailored for specific use cases.

- **`CustomerFacingPreset`**: Balanced protection for public bots (Budget, Injection, Jailbreak-Warn, PII-Redact).
- **`DeveloperToolsPreset`**: High-velocity, low-friction (Injection-Low, ToolGuards for shell/SQL, PII-Warn).
- **`FinancialServicesPreset`**: Strictest PII and tool guards (Passport/TaxID/Bank detection, SQL blocking, High sensitivity).
- **`HealthcarePreset`**: PHI focus (Blocks instead of redacts PII, high sensitivity, conservative rate limits).
- **`InternalToolsPreset`**: Lightweight security for trusted users (Injection-Low, PII-Warn).

---

## Custom Policy Example

```python
from claudekit.security import Policy

class NoSecretWordPolicy(Policy):
    name = "no_secret_word"
    
    def check_request(self, messages, context):
        for msg in messages:
            if "swordfish" in msg["content"].lower():
                from claudekit.errors import SecurityError
                raise SecurityError("Secret word detected!")

# Usage
layer = SecurityLayer([NoSecretWordPolicy()])
```

---

## Technical Considerations

1. **Trusted Callers.** Setting `trusted_caller=True` in `SecurityLayer.check_*` or the `SecurityContext` allows bypassing injection and jailbreak checks. Use this for recursive calls where the input is already validated.
2. **Fail-Open vs. Fail-Closed.** 
   - `JailbreakPolicy` fails-open (allows request) if the classifier model is unavailable to prevent blocking legitimate traffic due to upstream outages.
   - `OutputSchemaPolicy` behaviour is configurable via `on_failure` (`raise`, `return_raw`, `return_partial`).
3. **Regex performance.** `PIIPolicy` and `PromptInjectionPolicy` use compiled regular expressions. Complex custom patterns may impact latency on very large message histories.
4. **Backend Concurrency.** `BudgetPolicy` and `RateLimitPolicy` use in-memory store by default, which is NOT thread-safe for multi-process deployments. Implement the `Abstract*Backend` for Redis in production.
5. **Tool Result Extraction.** `PromptInjectionPolicy` specifically extracts and scans `tool_result` content blocks to prevent injection via external data sources.

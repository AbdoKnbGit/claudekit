# claudekit · precheck

Pre-flight token counting and context window validation. Prevents expensive surprises and "context window exceeded" errors by counting tokens BEFORE sending a request to the Anthropic API.

**Source files:** `_token_counter.py`

---

## Class: `TokenCountResult`

**Source:** `_token_counter.py:28`
**Type:** `@dataclass`

Result of a pre-flight token count.

### Attributes

| Attribute | Type | Default | Description |
|---|---|---|---|
| `input_tokens` | `int` | *(required)* | Number of input tokens counted. |
| `fits_in_context` | `bool` | *(required)* | `True` if `input_tokens` fits in the model's context window. |
| `estimated_input_cost` | `float` | *(required)* | Estimated input cost in USD based on the model registry. |
| `warning` | `Optional[str]` | — | Warning message if usage is high (e.g., >75%). |
| `model` | `str` | *(required)* | The API model ID used for counting. |
| `context_window` | `int` | `0` | The model's total context window size in tokens. |
| `percent_used` | `float` | `0.0` | Percentage of context window used (0.0-100.0). |

---

## Class: `TokenCounter`

**Source:** `_token_counter.py:55`

Uses the `count_tokens` SDK method to get precise token counts from the official API without incurring generation costs.

### Constructor

```python
TokenCounter(client: Any)
```

- **Parameters:** `client` — A `TrackedClient` or compatible Anthropic client.

### Methods

#### `count(model, messages, system=None, tools=None) -> TokenCountResult`

Counts tokens for a prospective request.

- **Args:**
  - `model`: Model ID to count for.
  - `messages`: List of message dictionaries.
  - `system`: Optional system prompt string.
  - `tools`: Optional list of tools (instances with `to_dict()` or raw dicts).
- **Behavior:** Attempts to call the underlying SDK's `client.messages.count_tokens()`.
- **Fallback:** If the API call fails (e.g., network issues or unsupported model), it falls back to a rough character-based estimate (approx. 4 characters per token).
- **Returns:** A `TokenCountResult` object.

#### `assert_fits(model, messages, max_percent=0.9, system=None, tools=None) -> None`

A guard method that raises an error if the request is too large.

- **Args:**
  - `max_percent`: Maximum allowed context usage (0.0 to 1.0). Defaults to `0.9` (90%).
- **Raises:** `TokenLimitError` if usage exceeds the threshold. The error includes a machine-readable code `TOKEN_LIMIT_EXCEEDED` and diagnostic context (tokens, limit, percent).
- **Example:**
  ```python
  counter.assert_fits("claude-sonnet-4-6", messages, max_percent=0.8)
  # Raises TokenLimitError if > 160k tokens used
  ```

---

## Module Exports (`__all__`)

2 names total:

| Name | Type | Description |
|---|---|---|
| `TokenCounter` | class | Main interface for pre-flight counting |
| `TokenCountResult` | dataclass | Data model for counting results |

---

## Edge Cases & Gotchas

1. **Tool definition counting.** The `count()` method automatically converts tool objects to dictionaries using their `to_dict()` method if available. This ensures tool schema overhead is included in the count.

2. **Estimate Fallback Accuracy.** The fallback estimator (`total_chars // 4`) is a very rough heuristic and should not be relied upon for precise budgeting. It is only used if the official API call fails.

3. **High Usage Warnings.** The `TokenCountResult.warning` attribute is automatically populated:
   - `percent_used >= 90`: "Near context limit (X.X% full)"
   - `percent_used >= 75`: "Context window X.X% used"

4. **Async Support.** `TokenCounter` currently uses sync API calls. If used within an async application, it will block the event loop during the `count_tokens` network call.

5. **`count_tokens` pricing.** While "count tokens" calls are generally free or very cheap on the Anthropic API, `claudekit` treats them as utility calls and does not record them in `SessionUsage` costs (which only tracks `create`/`stream`).

6. **Underlying Client.** `TokenCounter` detects if it's wrapping a `TrackedClient` and accesses the internal `_client` to ensure it's calling the raw SDK method without unnecessary proxying.

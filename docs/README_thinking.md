# claudekit · thinking

Helpers for managing Claude's extended thinking (reasoning) capabilities. Configure token budgets and extract internal thoughts from responses.

**Source files:** `_helpers.py`

---

## Configuration Helpers

These functions return the dictionary structure expected by the `thinking` parameter in the Anthropic Messages API.

### `thinking_adaptive(budget_tokens)`
**Source:** `_helpers.py:48`
Recommended for most use cases. Claude decides when extended thinking is beneficial for the given prompt.
- **`budget_tokens`**: The maximum number of tokens allocated for reasoning. Total `max_tokens` must be greater than this value.

### `thinking_enabled(budget_tokens)`
**Source:** `_helpers.py:22`
Forces Claude to use extended thinking for every response, up to the specified budget.

### `thinking_disabled()`
**Source:** `_helpers.py:74`
Explicitly disables extended thinking.

---

## Response Processing

### `extract_thinking(response)`
**Source:** `_helpers.py:87`
Claude's reasoned responses contain multiple content blocks. This utility separates internal reasoning from the final answer.

- **Input:** An `anthropic.types.Message` or any object with a `.content` list of blocks.
- **Output:** A tuple of `(thinking_text, answer_text)`.

```python
from claudekit.thinking import thinking_adaptive, extract_thinking

response = client.messages.create(
    model="claude-3-7-sonnet-20250219",
    max_tokens=4096,
    thinking=thinking_adaptive(budget_tokens=2048),
    messages=[{"role": "user", "content": "Explain the Reimann Hypothesis."}]
)

thoughts, answer = extract_thinking(response)
print(f"Claude's reasoning: {thoughts}")
print(f"Final answer: {answer}")
```

---

## Technical Considerations

1. **Token Budgets.** `budget_tokens` must be a positive integer. If a non-positive value is passed, a `ConfigurationError` is raised.
2. **Model Support.** Extended thinking is only supported by specific models (e.g., Claude 3.7 Sonnet). Using these helpers with unsupported models will result in an API error.
3. **Block Order.** Claude typically emits `thinking` blocks before `text` blocks. `extract_thinking` preserves this semantic order while joining multiple blocks of the same type with newlines.
4. **Streaming.** These helpers are designed for non-streaming responses. For streaming, you must inspect the `type` of individual `ContentBlockDeltaEvent` objects.

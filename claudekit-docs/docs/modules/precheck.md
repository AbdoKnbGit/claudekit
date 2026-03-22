---
title: Precheck
description: TokenCounter — pre-flight token counting using the count_tokens API to prevent context window overflows before sending expensive requests.
module: claudekit.precheck
classes: [TokenCounter, TokenCountResult]
---

# Precheck

`claudekit.precheck` provides `TokenCounter` — count tokens **before** sending a request to prevent expensive surprises or context window overflows.

## TokenCounter

```python
from claudekit import TrackedClient
from claudekit.precheck import TokenCounter

client  = TrackedClient()
counter = TokenCounter(client)
```

### count

Calls the `count_tokens` API and returns a `TokenCountResult`. Falls back to a character-based estimate (`chars / 4`) if the API call fails.

```python
result = counter.count(
    model="claude-sonnet-4-6",
    messages=[{"role": "user", "content": very_long_text}],
    system="You are a helpful assistant.",  # optional
    tools=[my_tool],                        # optional list of @tool wrappers or dicts
)
```

### assert_fits

Raises `TokenLimitError` if the request would exceed `max_percent` of the model's context window.

```python
counter.assert_fits(
    model="claude-sonnet-4-6",
    messages=messages,
    max_percent=0.9,    # default 0.9 = 90% of context window
    system=None,
    tools=None,
)
# Raises TokenLimitError if input_tokens > context_window * max_percent
```

---

## TokenCountResult

```python
result = counter.count("claude-haiku-4-5", messages)

result.input_tokens           # int — token count from the API (or estimate)
result.fits_in_context        # bool — True if tokens <= context_window
result.estimated_input_cost   # float — USD at input rate
result.context_window         # int — model's context window size
result.percent_used           # float — (input_tokens / context_window) * 100
result.warning                # str | None — set at 75% ("75% used") and 90% ("Near limit")
result.model                  # str — model ID used
```

---

## Typical patterns

### Guard before sending

```python
counter.assert_fits("claude-opus-4-6", messages, max_percent=0.8)
response = client.messages.create(model="claude-opus-4-6", messages=messages, max_tokens=2048)
```

### Check cost before long batch

```python
from claudekit.precheck import TokenCounter

counter = TokenCounter(client)
total_input_cost = 0.0
for batch_messages in all_batches:
    r = counter.count("claude-haiku-4-5", batch_messages)
    total_input_cost += r.estimated_input_cost

print(f"Estimated input cost for all batches: ${total_input_cost:.4f}")
```

### Warn when near limit

```python
result = counter.count("claude-sonnet-4-6", messages)
if result.warning:
    logger.warning("Context warning: %s", result.warning)
if not result.fits_in_context:
    # Split messages or use a model with larger context
    raise ValueError("Messages won't fit in context")
```

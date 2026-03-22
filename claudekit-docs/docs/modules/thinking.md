---
title: Thinking
description: Helpers for enabling extended thinking (always-on or adaptive) and extracting thinking blocks from responses.
module: claudekit.thinking
exports: [thinking_enabled, thinking_adaptive, thinking_disabled, extract_thinking]
---

# Thinking

`claudekit.thinking` provides three config helpers and one extraction helper for Claude's extended thinking feature. All active Claude models support thinking.

## Config helpers

Pass the returned dict to the `thinking=` parameter of `messages.create()`.

### thinking_enabled

Always activates the thinking phase before responding. Use for hard reasoning tasks.

```python
from claudekit.thinking import thinking_enabled

response = client.messages.create(
    model="claude-opus-4-6",
    max_tokens=16_000,   # must exceed budget_tokens
    thinking=thinking_enabled(budget_tokens=10_000),
    messages=[{"role": "user", "content": "Prove the Pythagorean theorem."}],
)
```

Returns `{"type": "enabled", "budget_tokens": 10000}`.

Raises `ConfigurationError` if `budget_tokens <= 0`.

### thinking_adaptive

Lets the model decide whether to think. Recommended for most use cases — cheaper on simple inputs, richer on complex ones.

```python
from claudekit.thinking import thinking_adaptive

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=8_000,
    thinking=thinking_adaptive(budget_tokens=5_000),
    messages=[{"role": "user", "content": "What is 2 + 2?"}],
)
```

Returns `{"type": "adaptive", "budget_tokens": 5000}`.

### thinking_disabled

Explicitly disables thinking (same as not passing `thinking=` at all).

```python
from claudekit.thinking import thinking_disabled

response = client.messages.create(
    model="claude-haiku-4-5",
    max_tokens=256,
    thinking=thinking_disabled(),
    messages=[{"role": "user", "content": "Hi"}],
)
```

Returns `{"type": "disabled"}`.

---

## extract_thinking

Splits a response into the model's internal reasoning and the final answer.

```python
from claudekit.thinking import extract_thinking

thoughts, answer = extract_thinking(response)
print(thoughts)   # The model's step-by-step reasoning (may be empty if no thinking blocks)
print(answer)     # The final text answer
```

**Returns** `(thinking_text: str, answer_text: str)`. Either may be an empty string if no blocks of that type are present.

**How it works:** iterates `response.content`, collects all `type="thinking"` blocks into `thoughts` and all `type="text"` blocks into `answer`, joined with newlines.

---

## Token budget guidance

| Task difficulty | Recommended `budget_tokens` | Notes |
|---|---|---|
| Simple | 1 000–2 000 | Classification, short Q&A |
| Moderate | 3 000–8 000 | Multi-step reasoning, code review |
| Complex | 10 000–20 000 | Proofs, architecture decisions |
| Max | 32 000 | Opus models; very expensive |

`max_tokens` must always exceed `budget_tokens` to leave room for the answer.

---

## Full example

```python
from claudekit import TrackedClient
from claudekit.thinking import thinking_adaptive, extract_thinking

client = TrackedClient()

response = client.messages.create(
    model="claude-opus-4-6",
    max_tokens=12_000,
    thinking=thinking_adaptive(budget_tokens=8_000),
    messages=[
        {"role": "user", "content": "Design a rate-limiting architecture for 10M req/day."}
    ],
)

thoughts, answer = extract_thinking(response)
print("=== Reasoning ===")
print(thoughts)
print("=== Answer ===")
print(answer)
print(f"Cost: ${client.usage.estimated_cost:.4f}")
```

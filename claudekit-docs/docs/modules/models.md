---
title: Models
description: Model registry with pricing, capabilities, and aliases for all Claude models. Includes select_model() for task-based model selection.
module: claudekit.models
exports: [MODELS, MODELS_BY_ID, get_model, select_model, ModelTask, Model]
---

# Models

`claudekit.models` provides a typed registry of every Claude model with accurate pricing, context windows, capability flags, deprecation status, and Bedrock/Vertex IDs.

## Active Models (as of 2026-03-20)

| Model | API ID | Input $/MTok | Output $/MTok | Context |
| --- | --- | --- | --- | --- |
| Claude Opus 4.6 | `claude-opus-4-6` | $5.00 | $25.00 | 1M |
| Claude Sonnet 4.6 | `claude-sonnet-4-6` | $3.00 | $15.00 | 1M |
| Claude Haiku 4.5 | `claude-haiku-4-5-20251001` | $1.00 | $5.00 | 200K |
| Claude Opus 4.5 | `claude-opus-4-5-20251101` | $5.00 | $25.00 | 200K |
| Claude Sonnet 4.5 | `claude-sonnet-4-5-20250929` | $3.00 | $15.00 | 200K |
| Claude Opus 4.1 | `claude-opus-4-1-20250805` | $15.00 | $75.00 | 200K |
| Claude Sonnet 4 | `claude-sonnet-4-20250514` | $3.00 | $15.00 | 200K |
| Claude Opus 4 | `claude-opus-4-20250514` | $15.00 | $75.00 | 200K |

All active models support thinking, vision, and streaming.

## Aliases

Short aliases resolve to the current snapshot:

| Alias | Resolves to |
| --- | --- |
| `claude-haiku-4-5` | `claude-haiku-4-5-20251001` |
| `claude-opus-4-5` | `claude-opus-4-5-20251101` |
| `claude-sonnet-4-5` | `claude-sonnet-4-5-20250929` |
| `claude-opus-4-1` | `claude-opus-4-1-20250805` |
| `claude-sonnet-4-0` | `claude-sonnet-4-20250514` |
| `claude-opus-4-0` | `claude-opus-4-20250514` |

## Usage

### Look up a model

```python
from claudekit.models import get_model

m = get_model("claude-haiku-4-5")          # alias works
m = get_model("claude-haiku-4-5-20251001") # full snapshot ID works too

m.api_id              # "claude-haiku-4-5-20251001"
m.name                # "Claude Haiku 4.5"
m.input_per_mtok      # 1.0  (USD per million input tokens)
m.output_per_mtok     # 5.0
m.context_window      # 200_000
m.max_output_tokens   # 64_000
m.supports_thinking   # True
m.supports_vision     # True
m.is_deprecated       # False
m.bedrock_id          # "anthropic.claude-haiku-4-5-20251001-v1:0"
m.vertex_id           # "claude-haiku-4-5@20251001"
```

### Estimate cost

```python
m = get_model("claude-sonnet-4-6")
cost = m.estimate_cost(
    input_tokens=1_000_000,
    output_tokens=200_000,
    cache_read_tokens=500_000,
    cache_write_tokens=100_000,
)
# 1M * $3.00 + 200K * $15.00 + 500K * $0.30 + 100K * $3.75 = $9.525
```

### Check context fit

```python
fits = m.fits_in_context(150_000)   # True if 150K <= context_window
```

### Task-based selection

```python
from claudekit.models import select_model, ModelTask

api_id = select_model(task=ModelTask.SIMPLE)    # cheapest capable model
api_id = select_model(task=ModelTask.BALANCED)  # price/performance balance
api_id = select_model(task=ModelTask.SMART)     # most capable
```

`ModelTask` values: `SIMPLE`, `BALANCED`, `SMART`, `FAST`, `THINKING`

### List all models

```python
from claudekit.models import MODELS

active = [m for m in MODELS if not m.is_deprecated]
thinking_models = [m for m in MODELS if m.supports_thinking and not m.is_deprecated]
cheapest = sorted(active, key=lambda m: m.input_per_mtok)[0]
```

### Direct lookup by ID

```python
from claudekit.models import MODELS_BY_ID

m = MODELS_BY_ID["claude-opus-4-6"]
```

## Model Dataclass

```python
@dataclass(frozen=True)
class Model:
    name: str                          # "Claude Haiku 4.5"
    api_id: str                        # "claude-haiku-4-5-20251001"
    aliases: tuple[str, ...]           # ("claude-haiku-4-5",)
    bedrock_id: str | None
    vertex_id: str | None
    input_per_mtok: float              # USD per million input tokens
    output_per_mtok: float
    cache_read_per_mtok: float         # 0.1x input (prompt cache)
    cache_write_per_mtok: float        # 1.25x input
    context_window: int                # tokens
    max_output_tokens: int
    supports_thinking: bool
    supports_vision: bool
    supports_streaming: bool
    is_deprecated: bool
    eol_date: str | None               # ISO-8601
    recommended_replacement: str | None
```

## Deprecation Warnings

`TrackedClient` automatically emits a `DeprecatedModelWarning` when a deprecated model is used:

```python
import warnings
from claudekit.errors import DeprecatedModelWarning

# Capture deprecation warnings
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    client.messages.create(model="claude-3-haiku-20240307", ...)
    if w:
        print(w[0].message)   # "Model 'claude-3-haiku-20240307' is deprecated (EOL 2026-04-20)."
```

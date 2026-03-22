# claudekit · models

Model registry, pricing data, and constraint-based selection. Provides a canonical list of all supported Claude models with their pricing, capabilities, and platform-specific identifiers, plus automatic model selection based on task complexity, budget, and feature requirements.

**Source files:** `_registry.py`, `_selector.py`

---

## Class: `Model`

**Source:** `_registry.py:16`
**Type:** `@dataclass(frozen=True)` — instances are immutable and hashable.

Represents a Claude model with its pricing, capabilities, and platform-specific identifiers.

### Attributes

| Attribute | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | *(required)* | Human-readable display name (e.g. `"Claude Sonnet 4.6"`). |
| `api_id` | `str` | *(required)* | Exact API model string with date snapshot (e.g. `"claude-sonnet-4-6"`). |
| `aliases` | `tuple[str, ...]` | `()` | Alternative API IDs that resolve to this model (e.g. `("claude-haiku-4-5",)` for `"claude-haiku-4-5-20251001"`). |
| `bedrock_id` | `Optional[str]` | `None` | AWS Bedrock model identifier. `None` if not available on Bedrock. |
| `vertex_id` | `Optional[str]` | `None` | Google Vertex AI model identifier. `None` if not available on Vertex. |
| `input_per_mtok` | `float` | `0.0` | Cost per **million** input tokens in USD. |
| `output_per_mtok` | `float` | `0.0` | Cost per **million** output tokens in USD. |
| `cache_read_per_mtok` | `float` | `0.0` | Cost per **million** cache-read tokens (typically 0.1× input). |
| `cache_write_per_mtok` | `float` | `0.0` | Cost per **million** cache-write tokens (typically 1.25× input). |
| `context_window` | `int` | `200_000` | Maximum context window size in tokens. |
| `max_output_tokens` | `int` | `8_192` | Maximum output tokens the model can generate. |
| `supports_thinking` | `bool` | `False` | Whether extended thinking is supported. |
| `supports_vision` | `bool` | `True` | Whether image input is supported. |
| `supports_streaming` | `bool` | `True` | Whether streaming responses are supported. |
| `is_deprecated` | `bool` | `False` | Whether the model is deprecated or retired. |
| `eol_date` | `Optional[str]` | `None` | End-of-life date string in ISO-8601 format (e.g. `"2026-02-19"`). |
| `recommended_replacement` | `Optional[str]` | `None` | Suggested replacement model `api_id` when this model is deprecated. |

### Methods

#### `estimate_cost(input_tokens, output_tokens, cache_read_tokens=0, cache_write_tokens=0) -> float`

Estimates the cost in USD for given token counts.

```python
def estimate_cost(
    self,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `input_tokens` | `int` | *(required)* | Number of non-cached input tokens. |
| `output_tokens` | `int` | *(required)* | Number of output tokens. |
| `cache_read_tokens` | `int` | `0` | Number of cache-read tokens. |
| `cache_write_tokens` | `int` | `0` | Number of cache-write tokens. |

**Returns:** `float` — estimated cost in USD.

**Formula:**
```
cost = (input_tokens × input_per_mtok / 1,000,000)
     + (output_tokens × output_per_mtok / 1,000,000)
     + (cache_read_tokens × cache_read_per_mtok / 1,000,000)
     + (cache_write_tokens × cache_write_per_mtok / 1,000,000)
```

**Example:**
```python
model = MODELS_BY_ID["claude-sonnet-4-6"]
model.estimate_cost(1_000_000, 0)        # 3.0  (input only)
model.estimate_cost(1000, 500)            # 0.0105
model.estimate_cost(0, 0, 1_000_000, 0)  # 0.30  (cache read only)
```

---

#### `fits_in_context(token_count) -> bool`

Checks if the given token count fits within this model's context window.

```python
def fits_in_context(self, token_count: int) -> bool
```

| Parameter | Type | Description |
|---|---|---|
| `token_count` | `int` | Number of tokens to check. |

**Returns:** `bool` — `True` if `token_count <= self.context_window`.

---

## Registered Models (`MODELS`)

**Source:** `_registry.py:114`
**Type:** `list[Model]`
**Pricing last verified:** 2026-03-20

### Latest (Active)

| Name | `api_id` | Aliases | Input/MTok | Output/MTok | Context | Max Output | Thinking |
|---|---|---|---|---|---|---|---|
| Claude Opus 4.6 | `claude-opus-4-6` | — | $5.00 | $25.00 | 1,000,000 | 128,000 | ✅ |
| Claude Sonnet 4.6 | `claude-sonnet-4-6` | — | $3.00 | $15.00 | 1,000,000 | 64,000 | ✅ |
| Claude Haiku 4.5 | `claude-haiku-4-5-20251001` | `claude-haiku-4-5` | $1.00 | $5.00 | 200,000 | 64,000 | ✅ |

### Legacy (Active, superseded)

| Name | `api_id` | Aliases | Input/MTok | Output/MTok | Context | Max Output | Thinking |
|---|---|---|---|---|---|---|---|
| Claude Opus 4.5 | `claude-opus-4-5-20251101` | `claude-opus-4-5` | $5.00 | $25.00 | 200,000 | 64,000 | ✅ |
| Claude Sonnet 4.5 | `claude-sonnet-4-5-20250929` | `claude-sonnet-4-5` | $3.00 | $15.00 | 200,000 | 64,000 | ✅ |
| Claude Opus 4.1 | `claude-opus-4-1-20250805` | `claude-opus-4-1` | $15.00 | $75.00 | 200,000 | 32,000 | ✅ |
| Claude Sonnet 4 | `claude-sonnet-4-20250514` | `claude-sonnet-4-0` | $3.00 | $15.00 | 200,000 | 64,000 | ✅ |
| Claude Opus 4 | `claude-opus-4-20250514` | `claude-opus-4-0` | $15.00 | $75.00 | 200,000 | 32,000 | ✅ |
| Claude Haiku 3.5 | `claude-3-5-haiku-20241022` | `claude-haiku-3-5` | $0.80 | $4.00 | 200,000 | 8,192 | ❌ |

### Deprecated / Retired

| Name | `api_id` | EOL Date | Replacement | Input/MTok | Thinking |
|---|---|---|---|---|---|
| Claude Sonnet 3.7 | `claude-3-7-sonnet-20250219` | 2026-02-19 | `claude-sonnet-4-6` | $3.00 | ✅ |
| Claude Haiku 3 | `claude-3-haiku-20240307` | 2026-04-20 | `claude-haiku-4-5-20251001` | $0.25 | ❌ |
| Claude Opus 3 | `claude-3-opus-20240229` | 2026-01-05 | `claude-opus-4-6` | $15.00 | ❌ |

### Platform IDs

| Model | Bedrock ID | Vertex ID |
|---|---|---|
| Opus 4.6 | `anthropic.claude-opus-4-6-v1` | `claude-opus-4-6` |
| Sonnet 4.6 | `anthropic.claude-sonnet-4-6` | `claude-sonnet-4-6` |
| Haiku 4.5 | `anthropic.claude-haiku-4-5-20251001-v1:0` | `claude-haiku-4-5@20251001` |
| Opus 4.5 | `anthropic.claude-opus-4-5-20251101-v1:0` | `claude-opus-4-5@20251101` |
| Sonnet 4.5 | `anthropic.claude-sonnet-4-5-20250929-v1:0` | `claude-sonnet-4-5@20250929` |
| Opus 4.1 | `anthropic.claude-opus-4-1-20250805-v1:0` | `claude-opus-4-1@20250805` |
| Sonnet 4 | `anthropic.claude-sonnet-4-20250514-v1:0` | `claude-sonnet-4@20250514` |
| Opus 4 | `anthropic.claude-opus-4-20250514-v1:0` | `claude-opus-4@20250514` |

### Cache Pricing (all models)

Cache pricing follows a consistent formula:
- **Cache read:** 0.1× input price
- **Cache write:** 1.25× input price

| Model Tier | Input | Cache Read | Cache Write |
|---|---|---|---|
| Opus ($15/MTok) | $15.00 | $1.50 | $18.75 |
| Opus ($5/MTok) | $5.00 | $0.50 | $6.25 |
| Sonnet ($3/MTok) | $3.00 | $0.30 | $3.75 |
| Haiku 4.5 ($1/MTok) | $1.00 | $0.10 | $1.25 |
| Haiku 3.5 ($0.80/MTok) | $0.80 | $0.08 | $1.00 |
| Haiku 3 ($0.25/MTok) | $0.25 | $0.03 | $0.30 |

---

## Lookup Dictionaries

### `MODELS_BY_ID: dict[str, Model]`

Maps every `api_id` **and** every alias to its `Model` object. Built by `_build_lookup()` at module load time.

```python
MODELS_BY_ID["claude-haiku-4-5-20251001"]  # → Model(name='Claude Haiku 4.5', ...)
MODELS_BY_ID["claude-haiku-4-5"]           # → same Model (via alias)
```

### `MODELS_BY_NAME: dict[str, Model]`

Maps the human-readable `name` to its `Model` object.

```python
MODELS_BY_NAME["Claude Haiku 4.5"]  # → Model(name='Claude Haiku 4.5', ...)
```

---

## Function: `get_model`

**Source:** `_registry.py:343`

```python
def get_model(model_id: str) -> Optional[Model]
```

Looks up a model by its API ID or alias. Both full snapshot IDs and short aliases are supported.

| Parameter | Type | Description |
|---|---|---|
| `model_id` | `str` | The API model identifier string (e.g. `"claude-haiku-4-5"` or `"claude-haiku-4-5-20251001"`). |

**Returns:** `Optional[Model]` — the matched `Model`, or `None` if not found.

```python
get_model("claude-haiku-4-5-20251001")  # → Model(name='Claude Haiku 4.5', ...)
get_model("claude-haiku-4-5")           # → same Model (alias)
get_model("nonexistent-model")          # → None
```

---

## Enum: `ModelTask`

**Source:** `_selector.py:19`
**Inherits:** `enum.Enum`

Task complexity levels for automatic model selection.

| Member | Value | Description | Maps to |
|---|---|---|---|
| `SIMPLE` | `"simple"` | Low-complexity tasks — classification, extraction, short Q&A | `claude-haiku-4-5` |
| `BALANCED` | `"balanced"` | Medium-complexity tasks — summarisation, code generation, multi-step reasoning | `claude-sonnet-4-6` |
| `COMPLEX` | `"complex"` | High-complexity tasks — research, long-form writing, advanced analysis | `claude-opus-4-6` |

---

## Function: `select_model`

**Source:** `_selector.py:120`

```python
def select_model(
    task: Optional[ModelTask] = None,
    max_cost_usd: Optional[float] = None,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    require_thinking: bool = False,
    require_vision: bool = False,
    prefer_speed: bool = False,
    platform: str = "anthropic",
) -> str
```

Picks the best Claude model given a set of constraints. Returns the **platform-specific model identifier string** (not a `Model` object).

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `task` | `Optional[ModelTask]` | `None` | Desired complexity tier. When `None`, defaults to `ModelTask.BALANCED`. |
| `max_cost_usd` | `Optional[float]` | `None` | Maximum acceptable cost in USD. Only effective when `input_tokens` and `output_tokens` are also provided. |
| `input_tokens` | `Optional[int]` | `None` | Estimated input tokens for cost filtering. |
| `output_tokens` | `Optional[int]` | `None` | Estimated output tokens for cost filtering. |
| `require_thinking` | `bool` | `False` | If `True`, only consider models with `supports_thinking=True`. |
| `require_vision` | `bool` | `False` | If `True`, only consider models with `supports_vision=True`. |
| `prefer_speed` | `bool` | `False` | If `True`, prefer the cheapest eligible model (lowest `input_per_mtok`). |
| `platform` | `str` | `"anthropic"` | Target platform. One of: `"anthropic"`, `"bedrock"`, `"vertex"`, `"foundry"`. |

### Returns

`str` — the platform-specific model identifier string.

### Raises

`ValueError` — if no model satisfies all constraints, or the platform is unknown.

### Selection Algorithm (5 steps)

1. **Build candidate pool.** Start with all models in `MODELS`.
2. **Hard-requirement filters.** Remove models that don't support `require_thinking` or `require_vision`. Filter by platform availability (e.g. models without `bedrock_id` are excluded when `platform="bedrock"`).
3. **Budget filter.** If `max_cost_usd`, `input_tokens`, and `output_tokens` are all provided, keep only models whose `estimate_cost()` ≤ `max_cost_usd`. If no model is affordable, keep all and log a warning (will return the cheapest below).
4. **Task-based or speed-based selection.**
   - If `prefer_speed=True`: sort by `input_per_mtok` ascending, pick first (cheapest).
   - If `task` is given: find the mapped model in candidates. If filtered out, pick the most capable remaining (sorted by cost descending).
   - If `task=None`: default to `ModelTask.BALANCED` behavior.
5. **Deprecation handling.** Follow the `recommended_replacement` chain. Emit `DeprecationWarning` and log at WARNING. If no valid replacement, return the deprecated model as-is.

### Examples

```python
# Simple task → Haiku
select_model(task=ModelTask.SIMPLE)
# → "claude-haiku-4-5"

# Complex on Bedrock → Bedrock Opus ID
select_model(task=ModelTask.COMPLEX, platform="bedrock")
# → "anthropic.claude-opus-4-6-v1"

# Budget-constrained
select_model(max_cost_usd=0.01, input_tokens=10_000, output_tokens=2_000)
# → "claude-haiku-4-5"  (cheapest that fits)

# Thinking + speed
select_model(require_thinking=True, prefer_speed=True)
# → "claude-haiku-4-5"  (cheapest with thinking support)
```

---

## Internal Helper Functions (`_selector.py`)

### `_id_matches(model: Model, target_id: str) -> bool`

Checks if `target_id` matches the model's `api_id` or any of its aliases.

### `_platform_id(model: Model, platform: str) -> str`

Returns the model identifier for the requested platform. Raises `ValueError` for unknown platforms or models without the platform's ID.

**Platform mapping:**
- `"anthropic"` → `model.api_id`
- `"bedrock"` → `model.bedrock_id` (raises `ValueError` if `None`)
- `"vertex"` → `model.vertex_id` (raises `ValueError` if `None`)
- `"foundry"` → `model.api_id` (same as anthropic)

### `_resolve_deprecation(model: Model) -> Model`

Follows the `recommended_replacement` chain for deprecated models. Emits `DeprecationWarning` and logs at WARNING for each hop. Detects cycles via a visited set. Returns a non-deprecated `Model`, or the original if no replacement is available.

### `_TASK_MAP: dict[ModelTask, str]`

Static mapping from `ModelTask` to default model alias:

| Task | Model alias |
|---|---|
| `SIMPLE` | `"claude-haiku-4-5"` |
| `BALANCED` | `"claude-sonnet-4-6"` |
| `COMPLEX` | `"claude-opus-4-6"` |

---

## Module Exports (`__all__`)

7 names total:

| Name | Type | Description |
|---|---|---|
| `Model` | `dataclass` | Model definition with pricing and capabilities |
| `MODELS` | `list[Model]` | All registered models |
| `MODELS_BY_ID` | `dict[str, Model]` | Lookup by `api_id` or alias |
| `MODELS_BY_NAME` | `dict[str, Model]` | Lookup by human-readable `name` |
| `ModelTask` | `enum.Enum` | Task complexity levels (SIMPLE/BALANCED/COMPLEX) |
| `get_model` | `function` | Look up a model by ID or alias |
| `select_model` | `function` | Constraint-based model selection |

---

## Edge Cases & Gotchas

1. **`Model` is frozen.** You cannot modify attributes after creation. Attempting `model.name = "x"` raises `FrozenInstanceError`.

2. **Aliases in `MODELS_BY_ID`.** Both `"claude-haiku-4-5"` and `"claude-haiku-4-5-20251001"` resolve to the same `Model` object. There is no distinction — they return the identical instance.

3. **Deprecated models still in `MODELS`.** They are not removed, just flagged with `is_deprecated=True`. `select_model()` will transparently swap them for their replacement.

4. **`select_model` returns a string, not a `Model`.** The return value is a platform-specific ID string (e.g. `"anthropic.claude-opus-4-6-v1"` for Bedrock). To get the `Model` object, use `get_model()` on the result.

5. **Budget fallback.** When no model fits within `max_cost_usd`, `select_model` does **not** raise — it logs a warning and returns the cheapest available model anyway.

6. **Foundry uses Anthropic IDs.** The `"foundry"` platform returns the same `api_id` as `"anthropic"`.

7. **`MODELS_BY_NAME` keys are human-readable.** Example: `"Claude Sonnet 4.6"`, not `"claude-sonnet-4-6"`. Case-sensitive.

8. **Haiku 3.5 is deprecated but active.** It's marked `is_deprecated=True` with `eol_date="2026-02-19"` and `recommended_replacement="claude-haiku-4-5-20251001"`. Selecting it will emit a `DeprecationWarning`.

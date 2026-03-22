# claudekit · client

Tracked Anthropic SDK client wrappers with automatic usage tracking. Records token counts, estimated costs, timing, and request IDs for every API call. Supports 4 platforms: Anthropic (direct), AWS Bedrock, Google Vertex AI, and Microsoft Foundry.

**Source files:** `_session.py`, `_tracked.py`, `_async_tracked.py`, `_bedrock.py`, `_vertex.py`, `_foundry.py`, `_factory.py`

---

## Architecture

```
TrackedClient          (wraps anthropic.Anthropic)
AsyncTrackedClient     (wraps anthropic.AsyncAnthropic)
TrackedBedrockClient   (wraps anthropic.AnthropicBedrock)
TrackedVertexClient    (wraps anthropic.AnthropicVertex)
TrackedFoundryClient   (wraps anthropic.AnthropicFoundry)
       │
       └── All share: .messages.create() / .messages.stream()
           └── Records → CallRecord → SessionUsage

create_client()  →  auto-detects platform from env vars
```

Platform clients use **lazy imports** — the package works even without `anthropic[bedrock]` or `anthropic[vertex]` installed. Instantiating a missing platform raises `PlatformNotAvailableError`.

---

## Class: `CallRecord`

**Source:** `_session.py:13`
**Type:** `@dataclass`

Record of a single API call.

### Attributes

| Attribute | Type | Default | Description |
|---|---|---|---|
| `model` | `str` | `""` | Model ID used for this call. |
| `input_tokens` | `int` | `0` | Number of input tokens. |
| `output_tokens` | `int` | `0` | Number of output tokens. |
| `cache_read_tokens` | `int` | `0` | Tokens read from prompt cache. |
| `cache_write_tokens` | `int` | `0` | Tokens written to prompt cache. |
| `estimated_cost` | `float` | `0.0` | Estimated cost in USD. |
| `timestamp` | `datetime` | `datetime.now()` | When the call was made. |
| `request_id` | `str` | `""` | API request ID from response headers. |
| `idempotency_key` | `str` | `""` | SDK idempotency key for deduplication. |
| `is_batch` | `bool` | `False` | Whether this was a batch API call (50% discount). |
| `duration_ms` | `float` | `0.0` | Call duration in milliseconds. |

---

## Class: `SessionUsage`

**Source:** `_session.py:47`
**Thread-safe:** All properties and methods use a `threading.Lock`.

Tracks API calls, tokens, and costs within a session.

### Constructor

```python
SessionUsage()
```

No parameters. Initializes empty call list and idempotency key set.

### Properties

| Property | Return Type | Description |
|---|---|---|
| `calls` | `list[CallRecord]` | Copy of all recorded calls. |
| `total_tokens` | `int` | Sum of `input_tokens + output_tokens` across all calls. |
| `total_input_tokens` | `int` | Sum of `input_tokens` across all calls. |
| `total_output_tokens` | `int` | Sum of `output_tokens` across all calls. |
| `estimated_cost` | `float` | Sum of `estimated_cost` across all calls. |
| `total_cost` | `float` | Alias for `estimated_cost`. |
| `call_count` | `int` | Number of recorded calls. |

### Methods

#### `record(call: CallRecord) -> None`

Records an API call. **Skips duplicate idempotency keys** — if a `CallRecord` has a non-empty `idempotency_key` that was already seen, it is silently ignored. This prevents counting SDK retries twice.

#### `breakdown() -> dict[str, dict]`

Per-model cost and token breakdown. Returns a dict mapping model ID to:

```python
{
    "input_tokens": int,
    "output_tokens": int,
    "cost": float,
    "call_count": int,
}
```

#### `export_csv() -> str`

Exports all calls as a CSV string with columns: `timestamp`, `model`, `input_tokens`, `output_tokens`, `cache_read`, `cache_write`, `cost`, `request_id`, `is_batch`.

#### `cache_savings() -> float`

Estimates USD savings from prompt cache hits. Cache reads cost 10% of normal input, so savings = 90% × cache_read_tokens × input_per_mtok. Uses the model registry for pricing.

#### `summary() -> str`

Returns a multi-line human-readable usage summary including call count, token counts, estimated cost, cache savings (if any), and per-model breakdown (if multiple models used).

#### `reset() -> None`

Clears all recorded calls and idempotency keys.

---

## Class: `TrackedClient`

**Source:** `_tracked.py:244`
**Wraps:** `anthropic.Anthropic`

Usage-tracking wrapper around the Anthropic SDK. Intercepts `messages.create()` and `messages.stream()` to record usage. All other SDK functionality is proxied through via `__getattr__`.

### Constructor

```python
TrackedClient(
    api_key: Optional[str] = None,
    *,
    security: Any = None,
    memory: Any = None,
    usage: Optional[SessionUsage] = None,
    **kwargs: Any,
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `api_key` | `Optional[str]` | `None` | Anthropic API key. Falls back to `ANTHROPIC_API_KEY` env var. |
| `security` | `Any` | `None` | Optional `SecurityLayer` instance. Keyword-only. |
| `memory` | `Any` | `None` | Optional `MemoryStore` instance. Keyword-only. |
| `usage` | `Optional[SessionUsage]` | `None` | Shared `SessionUsage` tracker. If `None`, creates a new one. Keyword-only. |
| `**kwargs` | `Any` | — | Additional kwargs forwarded to `anthropic.Anthropic()`. |

### Properties

| Property | Return Type | Description |
|---|---|---|
| `usage` | `SessionUsage` | The usage tracker for this client. |
| `security` | `Any` | The optional security layer. |
| `memory` | `Any` | The optional memory store. |
| `messages` | `_TrackedMessages` | The tracked messages resource. |
| `all_sessions_usage` | `SessionUsage` | Combined usage across main tracker and all inline sessions. |

### Methods

#### `messages.create(**kwargs) -> anthropic.types.Message`

Calls `anthropic.Anthropic().messages.create(**kwargs)`. Automatically:
1. Checks if the model is deprecated → emits `DeprecatedModelWarning`.
2. Extracts `idempotency_key` from kwargs (if present).
3. Times the call with `time.perf_counter()`.
4. Extracts usage from response: `input_tokens`, `output_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`.
5. Estimates cost using the model registry.
6. Records a `CallRecord` into `SessionUsage`.

All kwargs are forwarded verbatim. Exceptions propagate unmodified.

#### `messages.stream(**kwargs) -> _TrackedStreamWrapper`

Returns a context manager that wraps the SDK stream. Usage is recorded from `get_final_message()` when the stream context exits successfully. If the stream is not fully consumed or an exception occurs, no usage is recorded.

```python
with client.messages.stream(model="claude-haiku-4-5", max_tokens=100,
                            messages=[...]) as stream:
    for text in stream.text_stream:
        print(text)
# Usage recorded here on __exit__
```

#### `create_session() -> SessionUsage`

Creates a new inline session with its own `SessionUsage`. The session shares the same underlying API client but tracks usage independently. The session's usage is included in `all_sessions_usage`.

#### `with_options(**kwargs) -> TrackedClient`

Returns a new `TrackedClient` sharing the same `SessionUsage`, `security`, `memory`, and sessions. The underlying SDK client is cloned via `anthropic.Anthropic.with_options(**kwargs)`. Useful for adjusting per-request defaults (e.g., timeout) while keeping unified usage tracking.

#### `__getattr__(name) -> Any`

Proxies all attribute access not listed above to the underlying `anthropic.Anthropic` client. You can access any SDK property/method directly.

---

## Class: `AsyncTrackedClient`

**Source:** `_async_tracked.py:169`
**Wraps:** `anthropic.AsyncAnthropic`

Async counterpart of `TrackedClient`. Identical API surface, but `messages.create()` and `messages.stream()` are `async`.

### Constructor

```python
AsyncTrackedClient(
    api_key: Optional[str] = None,
    *,
    security: Any = None,
    memory: Any = None,
    usage: Optional[SessionUsage] = None,
    http_client: Any = None,
    **kwargs: Any,
)
```

Extra parameter vs `TrackedClient`:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `http_client` | `Any` | `None` | Optional `httpx.AsyncClient` for HTTP requests. |

### Async Methods

```python
response = await client.messages.create(model=..., max_tokens=..., messages=[...])

async with client.messages.stream(model=..., max_tokens=..., messages=[...]) as stream:
    async for text in stream.text_stream:
        print(text)
```

Properties and `create_session()` / `with_options()` / `all_sessions_usage` are identical to `TrackedClient`.

---

## Class: `TrackedBedrockClient`

**Source:** `_bedrock.py:171`
**Wraps:** `anthropic.AnthropicBedrock`
**Requires:** `pip install anthropic[bedrock]`

### Constructor

```python
TrackedBedrockClient(
    *,
    security: Any = None,
    memory: Any = None,
    usage: Optional[SessionUsage] = None,
    **kwargs: Any,
)
```

All parameters are keyword-only. No `api_key` — Bedrock uses AWS credentials. Common kwargs: `aws_region`, `aws_access_key`, `aws_secret_key`, `aws_session_token`.

**Raises:** `PlatformNotAvailableError` if `anthropic[bedrock]` is not installed.

Same API surface as `TrackedClient`: `.messages.create()`, `.messages.stream()`, `.usage`, `.create_session()`, `.with_options()`, `.all_sessions_usage`.

---

## Class: `TrackedVertexClient`

**Source:** `_vertex.py:171`
**Wraps:** `anthropic.AnthropicVertex`
**Requires:** `pip install anthropic[vertex]`

### Constructor

```python
TrackedVertexClient(
    *,
    security: Any = None,
    memory: Any = None,
    usage: Optional[SessionUsage] = None,
    **kwargs: Any,
)
```

Common kwargs: `project_id`, `region`.

**Raises:** `PlatformNotAvailableError` if `anthropic[vertex]` is not installed.

Same API surface as `TrackedClient`.

---

## Class: `TrackedFoundryClient`

**Source:** `_foundry.py:174`
**Wraps:** `anthropic.AnthropicFoundry`
**Requires:** Latest `anthropic` SDK with Foundry support.

### Constructor

```python
TrackedFoundryClient(
    *,
    security: Any = None,
    memory: Any = None,
    usage: Optional[SessionUsage] = None,
    **kwargs: Any,
)
```

**Raises:** `PlatformNotAvailableError` if `AnthropicFoundry` is not available.

Same API surface as `TrackedClient`.

---

## Function: `create_client`

**Source:** `_factory.py:19`

```python
def create_client(
    platform: Optional[str] = None,
    api_key: Optional[str] = None,
    security: Any = None,
    memory: Any = None,
    plugins: Any = None,
    **kwargs: Any,
) -> Any
```

Unified client factory with automatic platform detection.

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `platform` | `Optional[str]` | `None` | Explicit platform: `"anthropic"`, `"bedrock"`, `"vertex"`, `"foundry"`, or `None` for auto-detection. |
| `api_key` | `Optional[str]` | `None` | API key (only for `"anthropic"` platform). |
| `security` | `Any` | `None` | Security layer to attach. |
| `memory` | `Any` | `None` | Memory store to attach. |
| `plugins` | `Any` | `None` | Reserved for future use. Currently unused. |
| `**kwargs` | `Any` | — | Forwarded to the platform client constructor. |

### Platform Auto-Detection

When `platform=None`, reads environment variables in this order:

| Priority | Env Var | Value | Creates |
|---|---|---|---|
| 1 | `CLAUDE_CODE_USE_BEDROCK` | `"1"` | `TrackedBedrockClient` |
| 2 | `CLAUDE_CODE_USE_VERTEX` | `"1"` | `TrackedVertexClient` |
| 3 | `CLAUDE_CODE_USE_FOUNDRY` | `"1"` | `TrackedFoundryClient` |
| 4 | *(default)* | — | `TrackedClient` |

### Returns

A tracked client instance (type depends on platform).

### Raises

- `ValueError` — unknown platform string.
- `PlatformNotAvailableError` — required SDK extra not installed.

---

## Internal Helper Functions (`_tracked.py`)

### `_extract_usage(response) -> tuple[int, int, int, int]`

Extracts `(input_tokens, output_tokens, cache_read_tokens, cache_write_tokens)` from an API response. Returns `(0, 0, 0, 0)` if the response has no `usage` attribute. Cache tokens come from `usage.cache_read_input_tokens` and `usage.cache_creation_input_tokens`.

### `_extract_request_id(response) -> str`

Extracts the API request ID from `response._request_id`. Returns `""` if not available.

### `_estimate_cost(model_id, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, is_batch=False) -> float`

Estimates cost using the model registry. If the model is unknown, returns `0.0`. Batch calls get a 50% discount.

### `_check_deprecated(model_id) -> None`

Emits a `DeprecatedModelWarning` if the model is deprecated. Includes EOL date and recommended replacement in the warning message.

---

## Module Exports (`__all__`)

8 names total:

| Name | Type | Description |
|---|---|---|
| `TrackedClient` | class | Sync wrapper for `anthropic.Anthropic` |
| `AsyncTrackedClient` | class (lazy) | Async wrapper for `anthropic.AsyncAnthropic` |
| `TrackedBedrockClient` | class (lazy) | AWS Bedrock wrapper |
| `TrackedVertexClient` | class (lazy) | Google Vertex wrapper |
| `TrackedFoundryClient` | class (lazy) | Microsoft Foundry wrapper |
| `CallRecord` | dataclass | Single API call record |
| `SessionUsage` | class | Thread-safe usage aggregator |
| `create_client` | function | Auto-detecting client factory |

**Lazy imports:** `AsyncTrackedClient`, `TrackedBedrockClient`, `TrackedVertexClient`, and `TrackedFoundryClient` are loaded via module-level `__getattr__()` — they are not imported at module load time.

---

## Edge Cases & Gotchas

1. **Idempotency key deduplication.** If you set `idempotency_key` on a request and the SDK retries it, `SessionUsage` only records the first call. Duplicate keys are silently skipped.

2. **Stream usage is recorded on context exit.** If a stream is not consumed (e.g., exception mid-stream), no `CallRecord` is created. Only successful stream completion triggers recording.

3. **`with_options()` shares usage.** Creating a new client via `with_options()` shares the same `SessionUsage` instance. Both clients' calls appear in the same tracker.

4. **`all_sessions_usage` creates a new `SessionUsage`.** It aggregates by replaying all `CallRecord`s into a fresh tracker each time you access it. This is O(n) per access.

5. **Platform clients are lazy.** `from claudekit.client import TrackedBedrockClient` works even without `anthropic[bedrock]` installed. The `ImportError` only triggers on instantiation.

6. **`__getattr__` proxy.** Any method/attribute not explicitly defined on the tracked client is proxied to the underlying SDK client. For example, `client.beta`, `client.count_tokens`, etc. all work transparently.

7. **Cost estimation returns `0.0` for unknown models.** If the model ID is not in the registry (e.g., a new model not yet registered), the cost is silently `0.0`.

8. **`export_csv()` includes headers.** The CSV string includes a header row. Costs are formatted to 6 decimal places.

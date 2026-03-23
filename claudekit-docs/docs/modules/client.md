# Client

**Module:** `claudekit.client` · **Classes:** `TrackedClient`, `AsyncTrackedClient`, `TrackedBedrockClient`, `TrackedVertexClient`, `TrackedFoundryClient`, `SessionUsage`, `CallRecord`

`claudekit.client` provides drop-in wrappers around the Anthropic SDK that record usage on every call. All SDK functionality is proxied transparently — no behaviour changes, only observation.

## create_client

Auto-detects the platform from environment variables. Use this when you want a single entry point regardless of deployment target.

```python
from claudekit import create_client

client = create_client()
# Resolves automatically:
#   ANTHROPIC_API_KEY  → TrackedClient
#   AWS_* vars         → TrackedBedrockClient
#   GOOGLE_* vars      → TrackedVertexClient

# Or force a platform explicitly
client = create_client(platform="bedrock", aws_region="us-east-1")
client = create_client(platform="vertex", project="my-gcp-project")
```

---

## TrackedClient

Synchronous client. Wraps `anthropic.Anthropic`.

```python
from claudekit import TrackedClient

client = TrackedClient(api_key="sk-...")   # or reads ANTHROPIC_API_KEY

response = client.messages.create(
    model="claude-haiku-4-5",
    max_tokens=512,
    messages=[{"role": "user", "content": "Hello"}],
)
```

### Constructor

```python
TrackedClient(
    api_key: str | None = None,   # defaults to ANTHROPIC_API_KEY env var
    *,
    security: SecurityLayer | None = None,   # applied to every call
    memory: MemoryStore | None = None,       # available via .memory
    usage: SessionUsage | None = None,       # shared tracker (for multi-client setups)
    **kwargs,                                 # forwarded to anthropic.Anthropic()
)
```

### Usage tracking

```python
client.usage.call_count       # int — total calls made
client.usage.total_tokens     # int — input + output tokens combined
client.usage.total_input_tokens
client.usage.total_output_tokens
client.usage.estimated_cost   # float — USD
client.usage.total_cost       # float — alias for estimated_cost
client.usage.calls            # list[CallRecord] — copy of all call records
client.usage.summary()        # str — human-readable summary
client.usage.breakdown()      # dict — per-model breakdown
client.usage.export_csv()     # str — CSV of all call records
client.usage.cache_savings()  # float — USD saved by prompt caching
client.usage.reset()          # clear all records
```

### Per-model breakdown

```python
bd = client.usage.breakdown()
# {
#   "claude-haiku-4-5-20251001": {
#     "call_count": 3,
#     "input_tokens": 120,
#     "output_tokens": 85,
#     "cost": 0.000545,
#   }
# }
```

### Streaming

```python
with client.messages.stream(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Write a poem."}],
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)
# Usage is recorded automatically when the stream context exits.
```

### Create a sub-session

```python
session_usage = client.create_session()   # SessionUsage
# Use this tracker for a specific logical session
combined = client.all_sessions_usage      # aggregates all sessions + main
```

### with_options

```python
# Returns a new TrackedClient sharing the same usage tracker
fast_client = client.with_options(timeout=5.0)
```

---

## AsyncTrackedClient

Async counterpart of `TrackedClient`. Wraps `anthropic.AsyncAnthropic`.

```python
from claudekit import AsyncTrackedClient
import asyncio

async def main():
    client = AsyncTrackedClient(api_key="sk-...")
    response = await client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=128,
        messages=[{"role": "user", "content": "Hi"}],
    )
    print(client.usage.summary())

asyncio.run(main())
```

All `TrackedClient` usage properties work identically on `AsyncTrackedClient`.

### Async streaming

```python
async with await client.messages.stream(...) as stream:
    async for text in stream.text_stream:
        print(text, end="")
```

---

## Platform Clients

### AWS Bedrock

```python
from claudekit import TrackedBedrockClient

client = TrackedBedrockClient(
    region_name="us-east-1",
    # Uses boto3 credentials from environment / IAM role
)
response = client.messages.create(
    model="anthropic.claude-haiku-4-5-20251001-v1:0",
    max_tokens=512,
    messages=[{"role": "user", "content": "Hello from Bedrock"}],
)
```

### Google Vertex AI

```python
from claudekit import TrackedVertexClient

client = TrackedVertexClient(
    project="my-gcp-project",
    location="us-east5",
)
response = client.messages.create(
    model="claude-haiku-4-5@20251001",
    max_tokens=512,
    messages=[{"role": "user", "content": "Hello from Vertex"}],
)
```

### Azure AI Foundry

```python
from claudekit import TrackedFoundryClient

client = TrackedFoundryClient(
    endpoint="https://my-endpoint.openai.azure.com/",
    api_key="...",
)
```

---

## SessionUsage

`SessionUsage` is the usage tracker attached to every client via `.usage`.

```python
from claudekit.client import SessionUsage, CallRecord

usage = SessionUsage()
usage.record(CallRecord(
    model="claude-haiku-4-5",
    input_tokens=100,
    output_tokens=50,
    estimated_cost=0.00015,
    duration_ms=320.0,
))

usage.call_count       # 1
usage.total_tokens     # 150
usage.estimated_cost   # 0.00015
usage.export_csv()     # CSV string
```

---

## CallRecord

Dataclass recorded for each API call.

| Field | Type | Description |
| --- | --- | --- |
| `model` | `str` | Model API ID |
| `input_tokens` | `int` | Input token count |
| `output_tokens` | `int` | Output token count |
| `cache_read_tokens` | `int` | Cache-read token count |
| `cache_write_tokens` | `int` | Cache-write token count |
| `estimated_cost` | `float` | USD |
| `timestamp` | `datetime` | When the call was made |
| `request_id` | `str` | Anthropic request ID from response headers |
| `duration_ms` | `float` | Call duration in milliseconds |
| `is_batch` | `bool` | Whether this was a Batch API call |

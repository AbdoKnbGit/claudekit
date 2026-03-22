---
title: Batches
description: BatchBuilder (fluent request constructor) and BatchManager (submit, poll, cancel, and retrieve results from the Anthropic Message Batches API at 50% cost).
module: claudekit.batches
classes: [BatchBuilder, BatchManager, BatchResult, BatchStats]
---

# Batches

`claudekit.batches` wraps the Anthropic Message Batches API. Batches are processed asynchronously at 50% the regular per-token cost. Use them for high-volume, non-latency-sensitive workloads.

## BatchBuilder

Fluent builder for batch request payloads. Each `.add()` appends one request.

```python
from claudekit.batches import BatchBuilder

builder = (
    BatchBuilder(
        default_model="claude-haiku-4-5",  # default model for requests without model override
        default_max_tokens=256,            # default max_tokens
    )
    .add(
        custom_id="req-1",
        messages=[{"role": "user", "content": "Summarize this article: ..."}],
    )
    .add(
        custom_id="req-2",
        messages=[{"role": "user", "content": "Classify the sentiment: ..."}],
        model="claude-sonnet-4-6",   # per-request override
        max_tokens=512,
        system="You are a sentiment classifier.",
    )
    .add(
        custom_id="req-3",
        messages=[{"role": "user", "content": "Translate to French: ..."}],
        temperature=0.3,   # extra kwargs forwarded to the API
    )
)

requests = builder.build()   # list[dict] — ready to pass to BatchManager.submit()
len(builder)                 # 3
```

**Raises `ConfigurationError`** if `custom_id` is empty or `default_max_tokens <= 0`.

---

## BatchManager

Submit, poll, cancel, and retrieve results from the Batches API.

```python
from claudekit import TrackedClient
from claudekit.batches import BatchManager, BatchBuilder

client = TrackedClient()
bm = BatchManager(
    client,
    usage=None,                      # SessionUsage | None — costs recorded here at 50% rate
    sidecar_path="~/.myapp/batches.json",  # persist batch IDs across restarts; None to disable
)
```

### Submit

```python
# From a builder
batch_id = bm.submit_builder(builder)

# Or from a raw list
batch_id = bm.submit(requests, max_tokens=512)
# Returns str — the batch ID ("msgbatch_...")
```

### Poll and wait

```python
# Check status without blocking
status = bm.status(batch_id)
# status.processing_status: "in_progress" | "ended"
# status.request_counts: {total, processing, succeeded, errored, canceled, expired}

# Block until complete (async)
result = await bm.wait(
    batch_id,
    poll_interval=5.0,    # seconds between polls
    max_wait=3600.0,      # total timeout seconds
)

### Cancel

```python
bm.cancel(batch_id)   # raises BatchCancelledError if already cancelled
```

### Results

```python
result = await bm.wait(batch_id)

result.stats.total_requests    # int
result.stats.succeeded         # int
result.stats.errored           # int
result.stats.total_cost_usd    # float — estimated cost at 50% rate
result.stats.summary()         # str — human-readable summary

# Iterate over individual responses
for item in result.items:
    item.custom_id    # str — matches the custom_id you provided
    item.result       # dict — the API response for this request
    item.error        # str | None — error message if this request failed
```

### Sidecar persistence

Batch IDs are saved to `~/.claudekit/batches.json` by default. On startup, `BatchManager` loads existing IDs so you can resume polling after a process restart.

```python
pending = bm.list_pending()   # list[str] — IDs of in-progress batches
```

---

## Errors

| Exception | When raised |
|---|---|
| `BatchNotReadyError` | Polling when batch is still in progress |
| `BatchCancelledError` | Cancelling already-cancelled batch, or cancelled before completion |
| `BatchPartialFailureError` | All requests processed but some errored |

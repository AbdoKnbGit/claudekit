# claudekit · batches

Asynchronous large-scale processing using the Anthropic Message Batches API. Processes requests offline at a 50% cost discount.

**Source files:** `_builder.py`, `_manager.py`, `_result.py`

---

## Core Components

### `BatchBuilder`
**Source:** `_builder.py:19`
A fluent, chainable API for constructing batch request payloads.
- **`add(custom_id, messages, ...)`**: Appends a request to the batch. You must provide a unique `custom_id` to correlate results later.
- **Defaults:** Set a `default_model` and `default_max_tokens` at the builder level to avoid repetition.
- **Validation:** Ensures `custom_id` and `messages` are non-empty before building.

### `BatchManager`
**Source:** `_manager.py:33`
The primary interface for submitting and monitoring batches.
- **`submit_builder(builder)`**: Sends a built batch to the API and returns a `batch_id`.
- **`wait(batch_id)`**: An async helper that polls the API with **exponential backoff** until the batch is complete (or cancels).
- **Sidecar Persistence:** Automatically saves active batch IDs to `~/.claudekit/batches.json`. This allows the manager to track batches across application restarts.
- **Cost Tracking:** Specifically records usage into a `SessionUsage` tracker at the 50% batch discount rate compared to live API calls.

### `BatchResult` & `BatchStats`
**Source:** `_result.py:17, 69`
Containers for finished batch outcomes.
- **`stats`**: Provides a `summary()` string and per-category counts (`succeeded`, `failed`, `expired`, `cancelled`).
- **Filtering:** Use `result.succeeded()` or `result.failed()` to quickly access specific subsets of the result list.
- **Iteration:** `BatchResult` is iterable, yielding each result entry as a plain dictionary.

---

## Usage Example

```python
from claudekit.batches import BatchManager, BatchBuilder

bm = BatchManager(client)

# 1. Build a batch of 1000 requests
builder = BatchBuilder(default_model="claude-3-7-sonnet-20250219")
for i in range(1000):
    builder.add(f"id-{i}", [{"role": "user", "content": f"Task {i}"}])

# 2. Submit
batch_id = bm.submit_builder(builder)

# 3. Wait for completion (polls every ~30s by default)
result = await bm.wait(batch_id)

# 4. Process results
print(result.stats.summary()) # "Batch: 1000 succeeded, 0 failed ($0.450000)"
for entry in result.succeeded():
    print(f"{entry['custom_id']}: {entry['result']['message']['content'][0]['text']}")
```

---

## Technical Details

1. **50% Discount.** `BatchManager` automatically uses the `is_batch=True` flag when estimating costs, ensuring your statistics reflect the discounted pricing of the Anthropic Batches API.
2. **Sidecar Implementation.** Persistence uses a "write-to-tmp-and-swap" pattern (`tmp.replace(path)`) to prevent file corruption during power failures or crashes.
3. **Exponential Backoff.** `wait()` starts with a 30s poll interval and grows by 1.5x each time (capped at ~4 mins), balancing responsiveness with API rate-limit friendliness.
4. **Partial Failures.** If some requests in a batch fail while others succeed, `BatchManager` logs a warning but returns the `BatchResult` normally. It only raises `BatchCancelledError` if the *entire* batch was cancelled.
5. **JSONL Compatibility.** While the Anthropic API uses JSONL for results, `BatchManager` abstracts this away by providing a standard Python list of dictionaries.

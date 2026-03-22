# claudekit — Batches + Client Combined

Complete reference for `claudekit/batches/` and how it integrates with the client module.
Every feature documented with the actual code, real API output, cost numbers, and architecture notes.

---

## Table of contents

1. [The four files](#1-the-four-files)
2. [BatchBuilder — constructing requests](#2-batchbuilder--constructing-requests)
3. [BatchManager — submit, poll, cancel](#3-batchmanager--submit-poll-cancel)
4. [BatchResult + BatchStats — reading outcomes](#4-batchresult--batchstats--reading-outcomes)
5. [Shared SessionUsage — one cost view across all paths](#5-shared-sessionusage--one-cost-view-across-all-paths)
6. [Full combined scenario — three execution paths](#6-full-combined-scenario--three-execution-paths)
7. [Cost analysis — batch vs real-time](#7-cost-analysis--batch-vs-real-time)
8. [When to use which path](#8-when-to-use-which-path)
9. [Error handling and validation guards](#9-error-handling-and-validation-guards)
10. [Quick reference card](#10-quick-reference-card)

---

## 1. The four files

```
claudekit/batches/
├── __init__.py      exports BatchBuilder, BatchManager, BatchResult, BatchStats
├── _builder.py      fluent request list constructor
├── _manager.py      network layer: submit, poll, cancel, persist
└── _result.py       result container + aggregate stats dataclass
```

```python
from claudekit.batches import BatchBuilder, BatchManager, BatchResult, BatchStats
```

**Relation to the client module:**
`BatchManager` accepts any client that exposes a `.batches` attribute (mapped to `sdk.beta.messages.batches`). It records costs into a `SessionUsage` — the exact same class used by `TrackedClient`. This means batch costs and real-time call costs appear in the same tracker, same `summary()`, same `export_csv()`.

---

## 2. BatchBuilder — constructing requests

**File:** `_builder.py`

### What it does

Builds the list of request dicts the Anthropic Batch API expects. Chainable `.add()` calls, one per request. Validates inputs before anything hits the network.

### Code

```python
from claudekit.batches import BatchBuilder

builder = BatchBuilder(
    default_model="claude-haiku-4-5-20251001",
    default_max_tokens=120,
)

builder.add(
    custom_id="ticket-001",
    messages=[{"role": "user", "content": "My order hasn't arrived in 3 weeks."}],
    system="You are a support triage AI. Format: CATEGORY: <x>  REPLY: <sentence>",
)
builder.add(
    custom_id="ticket-002",
    messages=[{"role": "user", "content": "I was charged twice for the same item."}],
    # no system here — inherits nothing, uses the per-add system only
)

print(len(builder))       # 2
print(repr(builder))      # BatchBuilder(requests=2, default_model='claude-haiku-4-5-20251001')

requests = builder.build()
print(requests[0])
# {
#   "custom_id": "ticket-001",
#   "params": {
#     "model": "claude-haiku-4-5-20251001",
#     "max_tokens": 120,
#     "messages": [...],
#     "system": "..."
#   }
# }
```

### Output from the scenario

```
requests added : 5
default_model  : claude-haiku-4-5-20251001
default_max_tok: 120
built 5 request dicts
first request  : custom_id='ticket-001'
first params   : model='claude-haiku-4-5-20251001', max_tokens=120
```

### Constructor parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `default_model` | `str` | `"claude-haiku-4-5-20251001"` | Model used for every request that doesn't override it |
| `default_max_tokens` | `int` | `256` | Token cap used for every request that doesn't override it. Must be > 0 |

### `.add()` parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `custom_id` | `str` | yes | Your identifier for this request — returned with results. Must be non-empty |
| `messages` | `list` | yes | The message list for this request. Must be non-empty |
| `model` | `str \| None` | no | Override `default_model` for this request only |
| `max_tokens` | `int \| None` | no | Override `default_max_tokens` for this request only |
| `system` | `str \| None` | no | System prompt for this request |
| `**kwargs` | any | no | Extra params forwarded to the API (`temperature`, `thinking`, `tools`, etc.) |

### `.build()` returns

A `list[dict]` where each dict has:
- `"custom_id"` — your identifier string
- `"params"` — the full params dict (model, max_tokens, messages, system, any extras)

### `__len__` and `__repr__`

```python
len(builder)   # int — number of requests added so far
repr(builder)  # "BatchBuilder(requests=8, default_model='claude-haiku-4-5-20251001')"
```

---

## 3. BatchManager — submit, poll, cancel

**File:** `_manager.py`

### What it does

The network layer for batches. Submits to the API, persists the `batch_id` to disk, polls with exponential backoff until complete, collects results. Also handles cancellation and cost recording.

### Constructor

```python
from claudekit.batches import BatchManager
from claudekit.client import SessionUsage
from pathlib import Path

bm = BatchManager(
    client,                        # any object with .batches.create/retrieve/results/cancel
    usage=platform_usage,          # optional SessionUsage — defaults to a new one
    sidecar_path=Path("batches.json"),  # None to disable disk persistence
)
```

### Constructor parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `client` | any | required | A client with `.batches` attribute mapping to the Batch API |
| `usage` | `SessionUsage \| None` | `None` → new one | Where batch costs get recorded. Pass your shared tracker here |
| `sidecar_path` | `Path \| None` | `~/.claudekit/batches.json` | JSON file to persist batch IDs. Set `None` to disable |

### `.submit()` — from raw request list

```python
batch_id = bm.submit(requests)   # list of dicts from BatchBuilder.build()
```

### `.submit_builder()` — from a BatchBuilder

```python
batch_id = bm.submit_builder(builder)   # calls builder.build() internally
```

### Result

```
manager: BatchManager(batches=0)
batch_id: msgbatch_01FBN3SKtH8wnmnnXRHNt12W
batch submitted at: 18:42:14
```

> **Note:** `BatchManager(batches=0)` means the sidecar was empty (or `sidecar_path=None`). After `.submit()` the internal count increments.

### `.wait()` — async polling

```python
import asyncio

result = asyncio.run(bm.wait(
    batch_id,
    poll_interval=30.0,    # start polling every 30 seconds
    max_wait=86400.0,      # give up after 24 hours (default)
))
```

**Polling behaviour:** starts at `poll_interval`, multiplies by 1.5 each cycle, caps at `poll_interval × 8`. For the default 30s: 30 → 45 → 67 → 101 → 151 → 240s max.

**What it returns:** a `BatchResult` when `processing_status == "ended"`.

**What it raises:**
- `BatchNotReadyError` — if `max_wait` is exceeded
- `BatchCancelledError` — if the batch was fully cancelled

### `.cancel()` — request cancellation

```python
bm.cancel(batch_id)   # sends cancel request — doesn't wait for confirmation
```

### `.usage` property

```python
bm.usage   # the SessionUsage tracker — contains batch call records
```

### Sidecar persistence

Every time a batch is submitted, the `batch_id` is appended to a JSON file on disk:

```json
{
  "batch_ids": [
    "msgbatch_01FBN3SKtH8wnmnnXRHNt12W",
    "msgbatch_01DwTbRHrDD58xdUxUCVdhTh"
  ]
}
```

This means if your process dies while waiting, you can restart and resume waiting on the same batch using the saved ID. Set `sidecar_path=None` to disable.

### `__repr__`

```python
repr(bm)   # "BatchManager(batches=2)"  — number of submitted batches tracked
```

---

## 4. BatchResult + BatchStats — reading outcomes

**Files:** `_result.py`

### BatchStats — the aggregate numbers

```python
stats = result.stats

stats.succeeded     # int — requests that completed
stats.failed        # int — requests that errored
stats.expired       # int — requests that expired before processing
stats.cancelled     # int — requests that were cancelled
stats.total_cost    # float — total USD at 50% batch rate
stats.total         # property: succeeded + failed + expired + cancelled
stats.success_rate  # property: succeeded / total  (0.0–1.0)
stats.summary()     # str — one-line human readable
```

### Real output — 5-ticket batch

```
total     : 5
succeeded : 5
failed    : 0
expired   : 0
cancelled : 0
total_cost: $0.000790  (at 50% batch rate)
success_rate: 100%
summary   : Batch: 5 succeeded, 0 failed, 0 expired, 0 cancelled ($0.000790)
```

### Real output — 8-ticket batch

```
Batch stats: Batch: 8 succeeded, 0 failed, 0 expired, 0 cancelled ($0.001928)
```

### BatchResult — the entry container

```python
result = await bm.wait(batch_id)

len(result)            # int — total entries
result.stats           # BatchStats

# iterate all entries
for entry in result:
    cid   = entry["custom_id"]
    rtype = entry["result"]["type"]    # "succeeded" | "errored" | "expired" | "canceled"

# filter helpers
successes = result.succeeded()    # list — only type == "succeeded"
failures  = result.failed()       # list — only type != "succeeded"

repr(result)
# "BatchResult(entries=5, succeeded=5, failed=0)"
```

### Entry structure (succeeded)

```python
entry = {
    "custom_id": "ticket-001",
    "result": {
        "type": "succeeded",
        "message": {
            "id": "msg_...",
            "model": "claude-haiku-4-5-20251001",
            "role": "assistant",
            "stop_reason": "end_turn",
            "content": [
                {"type": "text", "text": "CATEGORY: SHIPPING\nREPLY: ..."}
            ],
            "usage": {
                "input_tokens": 82,
                "output_tokens": 52,
            }
        }
    }
}
```

### Accessing the reply text

```python
for entry in result.succeeded():
    text = entry["result"]["message"]["content"][0]["text"]
    tokens = entry["result"]["message"]["usage"]
    print(entry["custom_id"], "→", text)
    print("  tokens: in=%d out=%d" % (tokens["input_tokens"], tokens["output_tokens"]))
```

### Real output — classified tickets

```
[ticket-001]  ✓  succeeded
  tokens: in=82 out=52
  reply :
    CATEGORY: SHIPPING
    REPLY: I'm sorry to hear your order hasn't arrived yet—let me look into the status of order #A123...

[ticket-002]  ✓  succeeded
  tokens: in=77 out=42
  reply :
    CATEGORY: BILLING
    REPLY: I apologize for the duplicate charge—I'll help you resolve this right away...
```

---

## 5. Shared SessionUsage — one cost view across all paths

**This is the key integration point between batches and the client module.**

All three execution paths — `TrackedClient` (real-time), `AsyncTrackedClient` (async), and `BatchManager` (batch) — accept a `SessionUsage` in their constructor. Pass the same object to all three and you get one unified cost tracker.

```python
from claudekit.client import TrackedClient, AsyncTrackedClient, SessionUsage
from claudekit.batches import BatchManager

# one shared tracker
platform_usage = SessionUsage()

# three clients — all report into the same tracker
realtime = TrackedClient(api_key=KEY, usage=platform_usage)
async_c  = AsyncTrackedClient(api_key=KEY, usage=platform_usage)
bm       = BatchManager(sdk_wrapper, usage=platform_usage)

# ... make calls on all three ...

# one report covers everything
print(platform_usage.summary())
csv = platform_usage.export_csv()
```

### How batch records differ from sync records

When `BatchManager._record_entry_cost()` records a batch entry it sets `is_batch=True` on the `CallRecord`. The cost is already calculated at 50% via `_estimate_cost(..., is_batch=True)`. The CSV export includes the `is_batch` column so you can split them:

```
Columns: timestamp,model,input_tokens,output_tokens,cache_read,cache_write,cost,request_id,is_batch
Batch rows : 8    ← is_batch=True
Sync rows  : 7    ← is_batch=False
```

---

## 6. Full combined scenario — three execution paths

**Real scenario:** E-commerce support platform processing one full shift.

### Architecture

```
platform_usage (shared SessionUsage)
    │
    ├── TrackedClient      → VIP customers (real-time, full price)
    ├── AsyncTrackedClient → escalations (concurrent multi-turn)
    └── BatchManager       → regular queue (async, 50% cheaper)
```

### Part A — VIP real-time (`TrackedClient`)

```python
realtime_client = TrackedClient(api_key=KEY, usage=platform_usage)
session_vip = realtime_client.create_session()

resp = realtime_client.messages.create(
    model=HAIKU,
    max_tokens=80,
    system="You are a concise e-commerce support agent. Keep replies under 2 sentences.",
    messages=[{"role": "user", "content": "My $450 order was marked delivered but I never received it."}],
)
session_vip.record(platform_usage.calls[-1])
```

**Output:**
```
[VIP-Emma] 'My $450 order was marked delivered but I never received...'
→ I'm sorry to hear that! I'll help you resolve this. Please provide your order number...

[VIP-James] 'I need to change the delivery address on my order placed 10 min ago...'
→ I can help! Please provide your order number, and I'll check if we can still modify...

[VIP-Sofia] 'I was charged $89.99 but the site showed $79.99 at checkout...'
→ I apologize for that discrepancy. Could you please provide your order number...

VIP session: 3 calls | tokens: 234 | cost: $0.000654
```

**Why real-time here:** customers are waiting for a response. You cannot queue a VIP for 2+ minutes.

### Part B — Regular queue (`BatchBuilder + BatchManager`)

```python
builder = BatchBuilder(default_model=HAIKU, default_max_tokens=100)
for tid, content in REGULAR_TICKETS:
    builder.add(
        custom_id=tid,
        messages=[{"role": "user", "content": content}],
        system="Classify into [SHIPPING/BILLING/PRODUCT/ACCOUNT/PROMO]. Format: CATEGORY: <x>  REPLY: <one sentence>",
    )

batch_id = batch_manager.submit_builder(builder)
result   = asyncio.run(batch_manager.wait(batch_id, poll_interval=30.0))
```

**Output:**
```
Builder: BatchBuilder(requests=8, default_model='claude-haiku-4-5-20251001')
Submitted → batch_id: msgbatch_01DwTbRHrDD58xdUxUCVdhTh
Submitted at: 18:48:58
Done at:      18:53:04

Batch stats: Batch: 8 succeeded, 0 failed, 0 expired, 0 cancelled ($0.001928)

Classified tickets:
  REG-001 → SHIPPING
  REG-002 → SHIPPING
  REG-003 → PROMO
  REG-004 → PRODUCT
  REG-005 → SHIPPING
  REG-006 → ACCOUNT
  REG-007 → PRODUCT
  REG-008 → ACCOUNT

Batch session: 8 calls | tokens: 872 | cost: $0.001274  (50% rate)
```

**Why batch here:** 8 routine tickets, no one is watching a spinner. You submit once, pay half, get all 8 classified in ~4 minutes.

### Part C — Escalations (`AsyncTrackedClient` + `asyncio.gather`)

```python
async def handle_escalation(case):
    # Turn 1 — acknowledge
    r1 = await async_client.messages.create(
        model=HAIKU, max_tokens=80,
        system="You are a senior support agent handling an escalation.",
        messages=[{"role": "user", "content": case["issue"]}],
    )
    # Turn 2 — resolution steps
    r2 = await async_client.messages.create(
        model=HAIKU, max_tokens=80,
        system="You are a senior support agent handling an escalation.",
        messages=[
            {"role": "user",      "content": case["issue"]},
            {"role": "assistant", "content": r1.content[0].text},
            {"role": "user",      "content": "What exactly will you do right now to fix this?"},
        ],
    )
    return case["id"], r1.content[0].text, r2.content[0].text

# run both escalations concurrently
results = asyncio.run(asyncio.gather(*[handle_escalation(e) for e in ESCALATIONS]))
```

**Output:**
```
[ESC-Alice]
Turn 1: I'm genuinely sorry you've had to reach out multiple times without resolution—that's frustrating...
Turn 2: You're right to call that out—let me be specific instead of vague.
  Here's what I'm doing right now:
  1. Locating...

[ESC-Marco]
Turn 1: I'm really sorry you're dealing with this - duplicate charges are frustrating...
Turn 2: You're right to ask for specifics. Let me be direct:
  What I can do immediately:
  1. Locate your account...

Escalation session: 4 calls | tokens: 708 | cost: $0.001988
```

**Why async here:** two angry customers, 2-turn conversation each. With `asyncio.gather` both conversations run in parallel — 4 HTTP calls in 2 "rounds" instead of 4 sequential calls.

> **Note on escalation cost:** $0.001988 for only 4 calls vs $0.000654 for 3 VIP calls. Escalations cost ~3× more per call because multi-turn sends the full conversation history as context on turn 2 — input tokens nearly double. This is a real cost signal, not a bug.

### Part D — End-of-shift report

```python
print(f"VIP real-time  : {session_vip.call_count:2d} calls  ${session_vip.estimated_cost:.6f}")
print(f"Batch regular  : {session_batch.call_count:2d} calls  ${session_batch.estimated_cost:.6f}  (50% off)")
print(f"Escalations    : {session_escalate.call_count:2d} calls  ${session_escalate.estimated_cost:.6f}")
print(f"PLATFORM TOTAL : {platform_usage.call_count:2d} calls  ${platform_usage.estimated_cost:.6f}")

print(platform_usage.summary())
csv = platform_usage.export_csv()
```

**Output:**
```
┌─ Per-tier breakdown ──────────────────────────────┐
│  VIP real-time  :  3 calls  $0.000654             │
│  Batch regular  :  8 calls  $0.001274  (50% off)  │
│  Escalations    :  4 calls  $0.001988             │
├───────────────────────────────────────────────────┤
│  PLATFORM TOTAL : 15 calls  $0.003916             │
└───────────────────────────────────────────────────┘

Cost without batch API : $0.005190
Cost with batch API    : $0.003916
Saved by batching      : $0.001274

API Usage Summary
  Calls       : 15
  Input tokens : 970
  Output tokens: 844
  Total tokens : 1,814
  Est. cost    : $0.003916

CSV export: 16 rows  (1 header + 15 call records)
Columns: timestamp,model,input_tokens,output_tokens,cache_read,cache_write,cost,request_id,is_batch
Batch rows : 8
Sync rows  : 7
```

---

## 7. Cost analysis — batch vs real-time

### Numbers from the run

| Tier | Calls | Total tokens | Cost | Per call |
|------|-------|-------------|------|----------|
| VIP real-time | 3 | 234 | $0.000654 | $0.000218 |
| Batch regular | 8 | 872 | $0.001274 | $0.000159 |
| Escalations | 4 | 708 | $0.001988 | $0.000497 |
| **Platform total** | **15** | **1,814** | **$0.003916** | $0.000261 avg |

### Batch saving

The 8 regular tickets at full price would have been $0.002548. You paid $0.001274 — exactly 50%. The saving on this one shift was $0.001274. At 100 shifts/month with 50 regular tickets each that's over $7/month saved on Haiku alone. At scale with Sonnet or Opus the saving is proportionally larger because the absolute prices are higher.

### Why escalations cost more per call

Turn 2 of each escalation sends the full conversation history — the original issue, turn 1's response, and the follow-up question — as context. Input tokens nearly double between turn 1 and turn 2 even though the question is short. This is not a bug or an inefficiency — it's how multi-turn conversations work. It's a cost signal telling you that long conversations are expensive and worth routing carefully.

---

## 8. When to use which path

```
User is waiting for the answer right now
    → TrackedClient.messages.create()

No one is watching a spinner, responses can come back in minutes
    → BatchBuilder + BatchManager     (50% cheaper)

Multiple conversations need to run in parallel without blocking each other
    → AsyncTrackedClient + asyncio.gather

Mix of all three in the same application
    → Pass the same SessionUsage to all three clients
    → Use create_session() for per-tier sub-tracking
    → Call platform_usage.summary() at the end for one unified report
```

---

## 9. Error handling and validation guards

### BatchBuilder guards (raised before any network call)

```python
# zero max_tokens
BatchBuilder(default_max_tokens=0)
# ConfigurationError: default_max_tokens must be positive, got 0. [CONFIGURATION_ERROR]

# build with no requests added
BatchBuilder().build()
# ConfigurationError: Cannot build an empty batch -- add at least one request.
#   Hint: Call .add() before .build().

# empty custom_id
BatchBuilder().add("", [{"role":"user","content":"hi"}])
# ConfigurationError: custom_id must be a non-empty string. [CONFIGURATION_ERROR]

# empty messages
BatchBuilder().add("r1", [])
# ConfigurationError: messages must be non-empty for request 'r1'. [CONFIGURATION_ERROR]
```

### BatchManager guards

```python
# submit empty list
bm.submit([])
# ConfigurationError: Cannot submit an empty batch.
#   Hint: Add at least one request before submitting.
```

### BatchManager async guards

```python
# max_wait exceeded
# BatchNotReadyError: Batch msgbatch_... not ready after 3600s.

# batch was fully cancelled
# BatchCancelledError: Batch msgbatch_... was cancelled.
```

### Partial failure handling

If some requests succeed and some fail, `BatchManager` logs a warning but returns a `BatchResult` normally. You check programmatically:

```python
if result.stats.failed > 0:
    for entry in result.failed():
        err = entry["result"].get("error", {})
        print(f"Failed: {entry['custom_id']} — {err}")
```

---

## 10. Quick reference card

```python
# ── build ──────────────────────────────────────────────────────
builder = BatchBuilder(default_model=HAIKU, default_max_tokens=120)
builder.add("req-1", messages=[...], system="...")
builder.add("req-2", messages=[...], model="claude-sonnet-4-6", max_tokens=500)
requests = builder.build()   # list[dict]

# ── submit ─────────────────────────────────────────────────────
bm = BatchManager(client, usage=platform_usage, sidecar_path=None)
batch_id = bm.submit_builder(builder)
# or
batch_id = bm.submit(requests)

# ── wait ───────────────────────────────────────────────────────
result = asyncio.run(bm.wait(batch_id, poll_interval=30.0, max_wait=86400.0))

# ── read results ───────────────────────────────────────────────
result.stats.succeeded        # int
result.stats.total_cost       # float USD at 50% rate
result.stats.success_rate     # 0.0–1.0
result.stats.summary()        # str

for entry in result:
    entry["custom_id"]
    entry["result"]["type"]   # "succeeded" | "errored" | "expired" | "canceled"
    entry["result"]["message"]["content"][0]["text"]

result.succeeded()            # list — only succeeded entries
result.failed()               # list — only non-succeeded entries
len(result)                   # int — total entries

# ── cost tracking ──────────────────────────────────────────────
bm.usage.call_count           # int  — one record per succeeded entry
bm.usage.total_tokens         # int
bm.usage.estimated_cost       # float — already at 50% rate
bm.usage.export_csv()         # CSV string — is_batch column = True for all rows

# ── combined with client ────────────────────────────────────────
shared = SessionUsage()
realtime = TrackedClient(api_key=KEY, usage=shared)
async_c  = AsyncTrackedClient(api_key=KEY, usage=shared)
bm       = BatchManager(sdk_wrapper, usage=shared)
# all three feed into shared — one summary() covers everything
```

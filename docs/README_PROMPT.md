# claudekit · prompts

Versioned prompt storage, unified diff, and A/B comparison for managing prompt engineering workflows.

---

## Architecture

```
claudekit.prompts
│
├── PromptManager             ← main API: save, load, list, delete, diff,
│     │                                   render, compare, export, import_
│     └── JSONPromptStorage   ← storage backend (atomic JSON file writes)
│
├── PromptVersion             ← dataclass: name, version, system, user_template,
│                                          created_at, metadata
│                               .render(**vars) → rendered user message
│                               .to_dict() / .from_dict()
│
└── ComparisonResult          ← A/B test output:
                                versions, inputs, outputs, token_counts, costs
                                .print() → formatted table
                                .to_csv() → CSV export

Error (claudekit.errors):
  ClaudekitError
  └── SecurityError
      └── PromptInjectionError  ← raised when injection is detected in user input
```

---

## Quick start

```python
from claudekit.prompts import PromptManager
from claudekit import TrackedClient

pm = PromptManager("./prompts.json")   # or any path

# ── save versions ──────────────────────────────────────────────────────────────
pm.save("support", system="Be concise.",                       version="1.0")
pm.save("support", system="Be concise and empathetic.",        version="2.0",
        user_template="Issue: {issue}", metadata={"author": "alice"})

# ── diff ───────────────────────────────────────────────────────────────────────
print(pm.diff("support", "1.0", "2.0"))

# ── render ─────────────────────────────────────────────────────────────────────
user_msg = pm.render("support", version="2.0", issue="login keeps failing")

# ── compare via real API ───────────────────────────────────────────────────────
client = TrackedClient(api_key="...")
result = pm.compare(
    "support",
    versions=["1.0", "2.0"],
    inputs=["My payment was charged twice.", "App crashes on startup."],
    model="claude-haiku-4-5-20251001",
    client=client,
)
result.print()
print(result.to_csv())
```

---

## API reference

### `PromptVersion`

```python
PromptVersion(
    name: str,
    version: str,
    system: str,
    user_template: str = "",
    created_at: datetime = datetime.now(),
    metadata: dict = {},
)
```

| Field | Type | Description |
|---|---|---|
| `name` | `str` | Prompt family name (groups all versions together) |
| `version` | `str` | Version identifier — any string: `"1.0"`, `"v2-beta"`, `"prod"` |
| `system` | `str` | The system prompt text |
| `user_template` | `str` | Optional template with `{variable}` placeholders |
| `created_at` | `datetime` | Set automatically; used by `"latest"` lookup |
| `metadata` | `dict` | Arbitrary key/value pairs (author, notes, etc.) |

#### `render(**variables) -> str`

Renders `user_template` using Python's `.format(**variables)`. Returns `""` if `user_template` is empty.

#### `to_dict() -> dict` / `from_dict(data) -> PromptVersion`

Serialization/deserialization. `created_at` is stored as an ISO 8601 string and parsed back automatically.

---

### `JSONPromptStorage`

```python
JSONPromptStorage(path: str | Path = "./prompts.json")
```

Reads the file on construction; creates it if missing. Uses atomic writes (temp file + rename) to prevent corruption.

| Method | Returns | Description |
|---|---|---|
| `save(version)` | `None` | Append a version to storage |
| `load(name, version="latest")` | `PromptVersion \| None` | Load by name+version; `"latest"` returns highest `created_at` |
| `list(name)` | `list[PromptVersion]` | All versions for a name, sorted by `created_at` ascending |
| `delete(name, version)` | `bool` | Remove version; returns `False` if not found |
| `export(name)` | `dict` | `{"name": ..., "versions": [...]}` |
| `import_(data)` | `None` | Replace all versions for the name with the exported data |

---

### `PromptManager`

```python
PromptManager(storage_path: str | Path = "./prompts.json")
```

High-level wrapper around `JSONPromptStorage`. All methods delegate to the storage layer.

#### `save(name, system, version, user_template="", metadata=None) -> PromptVersion`

Creates and persists a new `PromptVersion`.

#### `load(name, version="latest") -> PromptVersion | None`

Returns `None` if not found. `"latest"` selects by highest `created_at`.

#### `list(name) -> list[PromptVersion]`

All versions sorted by `created_at`. Returns `[]` for unknown names.

#### `delete(name, version) -> bool`

Returns `True` if deleted, `False` if not found.

#### `diff(name, v1, v2) -> str`

Unified diff between `v1.system` and `v2.system`. Raises `ValueError` if either version is missing.

#### `render(name, version="latest", **variables) -> str`

Load a version and call `.render(**variables)`. Raises `ValueError` if not found.

#### `compare(name, versions, inputs, model, client) -> ComparisonResult`

Run A/B comparison. Makes **N × M API calls** (N versions × M inputs).

```python
result = pm.compare(
    "prompt_name",
    versions=["v1", "v2"],
    inputs=["test input 1", "test input 2"],
    model="claude-haiku-4-5-20251001",
    client=tracked_client,
)
```

- Raises `ValueError` if any version is missing.
- Each call uses `max_tokens=4096` — actual cost depends on response length.
- Cost is read from `response._estimated_cost` (set by `TrackedClient`); falls back to `0.0` for plain clients.

#### `export(name) -> dict`

Export all versions as a portable dict.

#### `import_(data: dict) -> None`

Import from an exported dict. Replaces all existing versions for that name.

---

### `ComparisonResult`

| Attribute | Type | Description |
|---|---|---|
| `versions` | `list[str]` | Version identifiers compared |
| `inputs` | `list[str]` | Input strings used |
| `outputs` | `dict[str, list[str]]` | `version → [output per input]` |
| `token_counts` | `dict[str, list[int]]` | `version → [output_tokens per input]` |
| `costs` | `dict[str, float]` | `version → total USD cost` (0.0 without TrackedClient) |

#### `print() -> None`

Prints a formatted table with truncated inputs/outputs (60 chars) and per-version costs.

#### `to_csv() -> str`

Returns a CSV string. Header row: `Input, v1, v2, ...`. One row per input.

---

### `PromptInjectionError`

```python
PromptInjectionError(
    message: str = "Prompt injection detected",
    *,
    code: str = "PROMPT_INJECTION_DETECTED",
    context: Optional[dict] = None,
    recovery_hint: Optional[str] = "Sanitise or reject the offending input.",
)
```

Inherits from `SecurityError → ClaudekitError`. Raise this when your application detects a prompt injection attempt in user input.

```python
from claudekit.errors import PromptInjectionError, PROMPT_INJECTION_DETECTED

if "ignore previous instructions" in user_input.lower():
    raise PromptInjectionError(
        "Injection detected",
        context={"input": user_input[:100], "score": 0.99},
    )
```

---

## Testing with real API calls

`compare()` makes real API calls — keep prompts short and inputs brief to minimise cost.

```python
import tempfile
from claudekit.prompts import PromptManager
from claudekit import TrackedClient

client = TrackedClient(api_key="...")

with tempfile.TemporaryDirectory() as tmp:
    pm = PromptManager(f"{tmp}/test.json")
    pm.save("classify", system="Reply with only: POSITIVE, NEGATIVE, or NEUTRAL.", version="v1")
    pm.save("classify", system="Reply with only: positive, negative, or neutral.", version="v2")

    result = pm.compare(
        "classify",
        versions=["v1", "v2"],
        inputs=["I love it!", "This is terrible."],
        model="claude-haiku-4-5-20251001",
        client=client,
    )
    print(result.to_csv())
    print(f"Cost: v1=${result.costs['v1']:.6f}  v2=${result.costs['v2']:.6f}")
```

---

## Notes and gotchas

1. **`compare()` always uses `max_tokens=4096`** — the parameter is hardcoded. Cost is determined by *actual* output length, not `max_tokens`. Use tightly constrained system prompts ("Reply with one word") to keep calls cheap.

2. **Cost tracking requires `TrackedClient`** — with a plain `anthropic.Anthropic` client, `response._estimated_cost` doesn't exist and `costs[v]` will be `0.0` for all versions. Pass a `TrackedClient` to get real cost data.

3. **`"latest"` is by `created_at`, not by version string sort** — `"2.0"` is not automatically "later" than `"1.0"`. Whichever was saved last (by wall clock) is returned as `"latest"`. Save versions in chronological order for predictable behavior.

4. **`import_()` replaces, not merges** — calling `import_()` replaces all versions for that prompt name with the imported data. Existing versions that are not in the import dict are deleted.

5. **`diff()` compares `system` fields only** — `user_template` and `metadata` differences are not included in the diff output.

6. **`render()` uses Python `.format()`** — extra variables in `**variables` that don't appear in the template are silently ignored. Missing variables raise a `KeyError`. Use `{varname}` syntax in templates (not `{{varname}}` which is a literal brace).

7. **Atomic writes on Windows** — `Path.replace()` is used for atomicity. On Windows this may fail if another process has the file open. For concurrent use, add external file locking.

8. **`PromptInjectionError` is not raised automatically** — claudekit does not scan inputs for injections. You must detect the pattern yourself and raise `PromptInjectionError` when appropriate.

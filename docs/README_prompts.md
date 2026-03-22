# claudekit · prompts

Versioned prompt storage, diffing, and A/B comparison. Provides a structured way to manage system prompts and user templates with JSON persistence, unified diff generation, and automated A/B testing across multiple model versions and inputs.

**Source files:** `_manager.py`, `_version.py`, `_storage.py`, `_comparison.py`

---

## Class: `PromptVersion`

**Source:** `_version.py:11`
**Type:** `@dataclass`

A single version of a named prompt.

### Attributes

| Attribute | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | *(required)* | The prompt family name (e.g., `"customer_support"`). |
| `version` | `str` | *(required)* | Version identifier (e.g., `"1.0"`, `"2.1-beta"`). |
| `system` | `str` | *(required)* | The system prompt text. |
| `user_template` | `str` | `""` | Optional user message template with `{variable}` placeholders. |
| `created_at` | `datetime` | `now` | Timestamp when this version was created. |
| `metadata` | `dict[str, Any]` | `{}` | Arbitrary key/value pairs (author, notes, tags, etc.). |

### Methods

#### `render(**variables) -> str`

Renders the `user_template` using Python's `str.format()`.

- **Args:** `**variables` — Keyword arguments matching placeholders in the template.
- **Returns:** `str` — The rendered user message. Returns `""` if `user_template` is empty.
- **Example:**
  ```python
  pv = PromptVersion(name="test", version="1", system="", user_template="Hello {name}")
  pv.render(name="World")  # "Hello World"
  ```

#### `to_dict() -> dict` / `from_dict(data) -> PromptVersion`

Serialization helpers for JSON storage. `created_at` is preserved as an ISO-8601 string.

---

## Class: `PromptManager`

**Source:** `_manager.py:21`

The primary interface for managing prompts. Handles persistence via a pluggable storage backend (defaults to `JSONPromptStorage`).

### Constructor

```python
PromptManager(storage_path: str | Path = "./prompts.json")
```

- **Parameters:** `storage_path` — Path to the JSON file where prompts are stored.

### Methods

#### `save(name, system, version, user_template="", metadata=None) -> PromptVersion`

Creates and saves a new prompt version to storage.
- **Returns:** The created `PromptVersion` object.
- **Side Effect:** Atomically updates the storage file.

#### `load(name, version="latest") -> Optional[PromptVersion]`

Retrieves a specific prompt version.
- **Args:** `version` — Version string, or `"latest"` to get the version with the most recent `created_at` timestamp.
- **Returns:** `PromptVersion` or `None` if not found.

#### `list(name) -> list[PromptVersion]`

Lists all versions of a prompt family, sorted by `created_at` ascending.

#### `delete(name, version) -> bool`

Deletes a specific version from storage.
- **Returns:** `True` if found and deleted, `False` otherwise.

#### `diff(name, v1, v2) -> str`

Generates a unified diff between the `system` prompts of two versions.
- **Args:** `v1`, `v2` — Version identifiers.
- **Returns:** A string in unified diff format (compatible with `patch`).
- **Raises:** `ValueError` if either version is missing.

#### `compare(name, versions, inputs, model, client) -> ComparisonResult`

Runs an A/B test across multiple prompt versions and test inputs.
- **Args:**
  - `name`: Prompt family name.
  - `versions`: List of version strings to test.
  - `inputs`: List of user input strings.
  - `model`: Model ID to use for all requests.
  - `client`: A `TrackedClient` instance.
- **Behavior:** Makes $N$ versions $\times M$ inputs API calls. Each call uses the respective version's `system` prompt and the provided user input.
- **Returns:** A `ComparisonResult` object containing all outputs and metrics.

#### `render(name, version="latest", **variables) -> str`

Shortcut to load a version and call its `render` method.

#### `export(name) -> dict` / `import_(data) -> None`

Exports/imports all versions of a prompt name as a dictionary.

---

## Class: `ComparisonResult`

**Source:** `_comparison.py:12`
**Type:** `@dataclass`

Result container for prompt A/B testing.

### Attributes

| Attribute | Type | Description |
|---|---|---|
| `versions` | `list[str]` | List of versions compared. |
| `inputs` | `list[str]` | List of test inputs used. |
| `outputs` | `dict[str, list[str]]` | Map of `version -> list of model responses`. |
| `token_counts` | `dict[str, list[int]]` | Map of `version -> list of output token counts`. |
| `costs` | `dict[str, float]` | Map of `version -> total USD cost` (estimated). |

### Methods

#### `print() -> None`

Prints a formatted Markdown-like table to stdout showing inputs and the corresponding outputs for each version. Includes total cost per version at the bottom.

#### `to_csv() -> str`

Exports the comparison matrix to a CSV string.

---

## Class: `JSONPromptStorage`

**Source:** `_storage.py:16`

Low-level storage backend using a JSON file.

### Key Features
- **Atomic Writes:** Writes to a temporary file in the same directory and then uses `os.replace` (atomic on POSIX and Windows). This prevents data loss if a crash occurs during a save.
- **Directory Auto-creation:** Automatically creates parent directories if they don't exist.
- **Thread-Safety:** Note that `JSONPromptStorage` does **not** implement internal locking; the `PromptManager` should be treated as non-thread-safe for concurrent writes to the same file.

---

## Module Exports (`__all__`)

4 names total:

| Name | Type | Description |
|---|---|---|
| `PromptManager` | class | Main interface for prompt operations |
| `PromptVersion` | dataclass | Data model for a single version |
| `ComparisonResult` | dataclass | Result of A/B comparison |
| `JSONPromptStorage`| class | Persistence backend |

---

## Edge Cases & Gotchas

1. **`render()` vs `variables`.** If the `user_template` contains placeholders (e.g. `{name}`) but you don't provide the corresponding keyword argument to `render()`, it will raise a `KeyError`.

2. **`latest` version logic.** The `"latest"` version is strictly determined by the `created_at` timestamp, not by alphanumeric version sorting or insertion order.

3. **Storage file size.** Since it's a single JSON file, it is loaded entirely into memory on initialization. Large numbers of prompts/versions with very long text may impact performance.

4. **Internal estimate_cost.** `PromptManager.compare` uses `response._estimated_cost`. Ensure you are using a `TrackedClient` so these attributes are populated.

5. **`import_` overwrites.** The `import_` method replaces the entire version history for that prompt name in the internal data dictionary.

6. **Unified Diff context.** `diff()` uses `difflib.unified_diff` with default context lines (3). It only compares the `system` field; `user_template` changes are not included in the diff.

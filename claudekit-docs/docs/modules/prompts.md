# Prompts

**Module:** `claudekit.prompts` · **Classes:** `PromptManager`, `PromptVersion`, `ComparisonResult`

`claudekit.prompts` provides `PromptManager` — version-controlled prompt storage with diff, A/B comparison, and variable template rendering. Uses JSON file storage by default.

## PromptManager

```python
from claudekit.prompts import PromptManager

pm = PromptManager(storage_path="./prompts.json")
# Default: "./prompts.json" in the current directory
```

### save

```python
pv = pm.save(
    name="support",                         # prompt family name
    system="Be concise and helpful.",       # system prompt text
    version="1.0",                          # version string
    user_template="Help with: {topic}",     # optional {variable} template
    metadata={"author": "alice"},           # optional metadata
)
# Returns PromptVersion
```

### load

```python
pv = pm.load("support", version="1.0")    # specific version
pv = pm.load("support", version="latest") # most recent by created_at
# Returns PromptVersion | None
```

### list / delete

```python
versions = pm.list("support")             # list[PromptVersion] sorted by created_at
pm.delete("support", version="1.0")       # bool — True if found and deleted
```

### diff

Unified diff between two versions of a prompt.

```python
diff_text = pm.diff("support", "1.0", "2.0")
print(diff_text)
# --- support v1.0
# +++ support v2.0
# @@ -1 +1 @@
# -Be concise and helpful.
# +Be concise, empathetic, and helpful.
```

**Raises `ValueError`** if either version is not found.

### render

Render a prompt's user template with variable substitution.

```python
message = pm.render("support", version="latest", topic="billing", user="Alice")
# "Help with: billing"  (if user_template="Help with: {topic}")
```

### compare (A/B test)

Run N versions × M inputs. Makes `N × M` API calls.

```python
from claudekit import TrackedClient

client = TrackedClient()
result = pm.compare(
    name="support",
    versions=["1.0", "2.0"],
    inputs=["How do I reset my password?", "Can I get a refund?"],
    model="claude-haiku-4-5",
    client=client,
    confirm=True,     # required if estimated cost > $0.10
)
```

**Returns `ComparisonResult`:**

```python
result.versions      # list[str] — ["1.0", "2.0"]
result.inputs        # list[str]
result.outputs       # dict[version, list[str]] — output for each (version, input) pair
result.token_counts  # dict[version, list[int]] — output tokens per call
result.costs         # dict[version, float] — total cost per version
```

### export / import_

```python
data = pm.export("support")    # dict — full version history
pm.import_(data)               # restore from exported dict
```

---

## PromptVersion

```python
from claudekit.prompts._version import PromptVersion

pv.name              # str — prompt family name
pv.version           # str
pv.system            # str — system prompt text
pv.user_template     # str — "{variable}" template (may be empty)
pv.metadata          # dict
pv.created_at        # datetime — UTC

text = pv.render(topic="billing")  # renders user_template with variable substitution
```

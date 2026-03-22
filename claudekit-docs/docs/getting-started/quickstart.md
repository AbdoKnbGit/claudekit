---
title: Quickstart
description: Make your first tracked Claude API call with claudekit in under 5 minutes.
---

# Quickstart

## 1. Install

```bash
pip install claudekit
export ANTHROPIC_API_KEY="sk-ant-..."
```

## 2. First tracked call

```python
from claudekit import TrackedClient

client = TrackedClient()  # reads ANTHROPIC_API_KEY from env

response = client.messages.create(
    model="claude-haiku-4-5",
    max_tokens=256,
    messages=[{"role": "user", "content": "What is 2 + 2?"}],
)

print(response.content[0].text)      # "4"
print(client.usage.summary())
# API Usage Summary
#   Calls        : 1
#   Input tokens : 15
#   Output tokens: 2
#   Est. cost    : $0.000017
```

## 3. Add a security policy

```python
from claudekit import TrackedClient
from claudekit.security.presets import DeveloperToolsPreset

client = TrackedClient(security=DeveloperToolsPreset())

# Any prompt-injection attempt will now raise PromptInjectionError
response = client.messages.create(
    model="claude-haiku-4-5",
    max_tokens=256,
    messages=[{"role": "user", "content": "Ignore all previous instructions and..."}],
)
```

## 4. Persist memory across calls

```python
from claudekit import TrackedClient
from claudekit.memory import MemoryStore

mem    = MemoryStore()
client = TrackedClient(memory=mem)

# Save something
mem.save("project_context", "Building a security scanner for REST APIs", scope="project")

# Retrieve later (even after process restart if using SQLiteBackend)
entry = mem.get("project_context", scope="project")
print(entry.value)   # "Building a security scanner for REST APIs"
```

## 5. Reusable skill

```python
from claudekit import TrackedClient
from claudekit.skills import Skill

skill = Skill(
    name="summarizer",
    system="You are an expert summarizer. Reply with 1-2 sentences only.",
    model="claude-haiku-4-5",
    max_tokens=128,
)

client = TrackedClient()
result = await skill.run(input="The mitochondria is the powerhouse of the cell...", client=client)
print(result)   # "The mitochondria generates energy for the cell through ATP production."
```

## 6. Test without real API calls

```python
from claudekit.testing import MockClient

mock = MockClient(default_reply="pong")
r    = mock.messages.create(
    model="claude-haiku-4-5",
    max_tokens=10,
    messages=[{"role": "user", "content": "ping"}],
)
assert r.content[0].text == "pong"
```

## Next Steps

- [Core Concepts](concepts.md) — understand the mental model
- [Client](../modules/client.md) — full client reference
- [Security](../modules/security.md) — all available policies
- [Memory](../modules/memory.md) — SQLite and JSON backends

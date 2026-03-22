---
title: Installation
description: How to install claudekit, requirements, and optional platform extras.
---

# Installation

## Requirements

- Python **3.11** or later
- `anthropic >= 0.40.0`

## Install

```bash
pip install claudekit
```

## Platform Extras

claudekit supports AWS Bedrock, Google Vertex AI, and Azure AI Foundry in addition to the default Anthropic API. Install the extra for the platform you need:

```bash
pip install claudekit[bedrock]    # AWS Bedrock
pip install claudekit[vertex]     # Google Vertex AI
pip install claudekit[otel]       # OpenTelemetry tracing (requires opentelemetry-api)
```

## Verify

```python
import claudekit
print(claudekit.__version__)
```

## API Key

Set your Anthropic API key as an environment variable:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

Or pass it directly to the client:

```python
from claudekit import TrackedClient
client = TrackedClient(api_key="sk-ant-...")
```

## Next Steps

→ [Quickstart](quickstart.md) — make your first tracked call

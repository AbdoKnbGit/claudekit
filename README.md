# claudekit

Production-grade Python framework for the Anthropic ecosystem.

claudekit wraps the Anthropic SDK, Agent SDK, MCP, and all deployment platforms (Bedrock, Vertex, Foundry) into one coherent framework. It adds usage tracking, typed security policies, persistent memory, multi-agent orchestration, session management, batch processing, versioned prompts, and a full testing layer — without replacing any underlying SDK. Every component is opt-in.

```bash
pip install claudekit
pip install claudekit[agent]   # Agent SDK support
pip install claudekit[mcp]     # MCP server builder
pip install claudekit[otel]    # OpenTelemetry tracing
pip install claudekit[all]     # Everything
```

```python
from claudekit import TrackedClient

client = TrackedClient()
response = client.messages.create(
    model="claude-haiku-4-5",
    max_tokens=256,
    messages=[{"role": "user", "content": "Hello"}],
)
print(client.usage.summary())
```

**[Documentation →](claudekit-docs/docs/index.md)**

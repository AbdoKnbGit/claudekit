"""Tracked Anthropic SDK client wrappers with usage tracking.

This module provides thin wrappers around the official Anthropic SDK clients
that automatically record token usage, estimated costs, and timing metadata
for every API call.  All wrappers share a unified :class:`SessionUsage`
interface for querying aggregate statistics.

Quick start::

    from claudekit.client import TrackedClient

    client = TrackedClient(api_key="sk-...")
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": "Hello!"}],
    )
    print(client.usage.summary())

Platform clients (Bedrock, Vertex, Foundry) use lazy imports so the package
works even when those optional SDK extras are not installed.  Attempting to
instantiate a platform client without the corresponding extra raises
:class:`~claudekit.errors.PlatformNotAvailableError` with the exact
``pip install`` command needed.

Auto-detection::

    from claudekit.client import create_client

    # Reads CLAUDE_CODE_USE_BEDROCK, CLAUDE_CODE_USE_VERTEX,
    # CLAUDE_CODE_USE_FOUNDRY from the environment.
    client = create_client()
"""

from __future__ import annotations

from claudekit.client._factory import create_client
from claudekit.client._session import CallRecord, SessionUsage
from claudekit.client._tracked import TrackedClient

# Lazy imports for platform clients to avoid hard dependencies.
# The actual classes are imported on first access or when explicitly imported
# by the caller.


def __getattr__(name: str) -> object:
    """Module-level ``__getattr__`` for lazy imports of platform clients.

    This allows ``from claudekit.client import TrackedBedrockClient`` to work
    without requiring the Bedrock/Vertex/Foundry SDK extras to be installed
    at module-import time.
    """
    if name == "AsyncTrackedClient":
        from claudekit.client._async_tracked import AsyncTrackedClient
        return AsyncTrackedClient

    if name == "TrackedBedrockClient":
        from claudekit.client._bedrock import TrackedBedrockClient
        return TrackedBedrockClient

    if name == "TrackedVertexClient":
        from claudekit.client._vertex import TrackedVertexClient
        return TrackedVertexClient

    if name == "TrackedFoundryClient":
        from claudekit.client._foundry import TrackedFoundryClient
        return TrackedFoundryClient

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "AsyncTrackedClient",
    "CallRecord",
    "SessionUsage",
    "TrackedBedrockClient",
    "TrackedClient",
    "TrackedFoundryClient",
    "TrackedVertexClient",
    "create_client",
]

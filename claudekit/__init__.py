"""claudekit -- Production-grade Python framework for the Anthropic ecosystem.

claudekit wraps the Anthropic Client SDK, Agent SDK, MCP, and all deployment
platforms into one coherent production framework.  It never replaces the
underlying SDKs -- it always stays compatible with their updates.

Quick start::

    from claudekit import TrackedClient, tool

    client = TrackedClient(api_key="sk-...")
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": "Hello!"}],
    )
    print(client.usage.summary())
"""

from __future__ import annotations

from claudekit._version import __version__
from claudekit.client._factory import create_client
from claudekit.client._session import CallRecord, SessionUsage
from claudekit.client._tracked import TrackedClient
from claudekit.errors import enable_rich_errors
from claudekit.tools._decorator import tool


def __getattr__(name: str) -> object:
    """Lazy imports for optional or heavy submodules."""

    # Async client
    if name == "AsyncTrackedClient":
        from claudekit.client._async_tracked import AsyncTrackedClient
        return AsyncTrackedClient

    # Platform clients
    if name == "TrackedBedrockClient":
        from claudekit.client._bedrock import TrackedBedrockClient
        return TrackedBedrockClient
    if name == "TrackedVertexClient":
        from claudekit.client._vertex import TrackedVertexClient
        return TrackedVertexClient
    if name == "TrackedFoundryClient":
        from claudekit.client._foundry import TrackedFoundryClient
        return TrackedFoundryClient

    # Security
    if name == "SecurityLayer":
        from claudekit.security._layer import SecurityLayer
        return SecurityLayer

    # Memory
    if name == "MemoryStore":
        from claudekit.memory._store import MemoryStore
        return MemoryStore

    # Sessions
    if name == "SessionManager":
        from claudekit.sessions._manager import SessionManager
        return SessionManager
    if name == "SessionConfig":
        from claudekit.sessions._config import SessionConfig
        return SessionConfig

    # Orchestration
    if name == "Orchestrator":
        from claudekit.orchestration._orchestrator import Orchestrator
        return Orchestrator

    # Testing
    if name == "MockClient":
        from claudekit.testing._mock_client import MockClient
        return MockClient

    # Errors
    if name == "ClaudekitError":
        from claudekit.errors._base import ClaudekitError
        return ClaudekitError

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "__version__",
    # Client
    "AsyncTrackedClient",
    "CallRecord",
    "create_client",
    "SessionUsage",
    "TrackedBedrockClient",
    "TrackedClient",
    "TrackedFoundryClient",
    "TrackedVertexClient",
    # Tools
    "tool",
    # Security
    "SecurityLayer",
    # Memory
    "MemoryStore",
    # Sessions
    "SessionConfig",
    "SessionManager",
    # Orchestration
    "Orchestrator",
    # Testing
    "MockClient",
    # Errors
    "ClaudekitError",
    "enable_rich_errors",
]

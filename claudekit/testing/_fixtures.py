"""pytest fixtures for claudekit testing.

Import these in your ``conftest.py``::

    from claudekit.testing._fixtures import *  # noqa: F403

Or selectively::

    from claudekit.testing._fixtures import mock_client, mock_anthropic
"""

from __future__ import annotations

from typing import Any, Generator

import pytest


@pytest.fixture
def mock_client() -> Any:
    """Provide a :class:`~claudekit.testing.MockClient` instance.

    The MockClient uses the existing high-level pattern-matching approach
    with ``construct()``-based responses.

    Yields:
        A fresh ``MockClient`` with strict mode enabled.
    """
    from claudekit.testing._mock_client import MockClient

    return MockClient(strict=True)


@pytest.fixture
def mock_anthropic() -> Any:
    """Provide a real ``anthropic.Anthropic`` backed by ``httpx.MockTransport``.

    The full SDK stack runs (auth, retries, Pydantic validation, error
    mapping) with zero network calls.

    Yields:
        A ``(client, handler)`` tuple. Register patterns via ``handler.on()``.
    """
    from claudekit.testing._mock_transport import create_mock_anthropic

    client, handler = create_mock_anthropic()
    return client, handler


@pytest.fixture
def tracked_client() -> Any:
    """Provide a :class:`~claudekit.client.TrackedClient` backed by MockTransport.

    Uses ``httpx.MockTransport`` under the hood so no real API calls are made,
    but the ``TrackedClient`` wrapper's usage tracking fully runs.

    Yields:
        A ``TrackedClient`` suitable for testing usage/session tracking.
    """
    from claudekit.client import TrackedClient
    from claudekit.testing._mock_transport import MockTransportHandler

    import httpx

    handler = MockTransportHandler(default_reply="tracked mock response")
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)

    import anthropic
    raw_client = anthropic.Anthropic(
        api_key="sk-ant-test-tracked",
        http_client=http_client,
    )

    return TrackedClient(_client=raw_client)


@pytest.fixture
def mock_agent_runner() -> Any:
    """Provide a :class:`~claudekit.testing.MockAgentRunner` instance.

    Yields:
        A fresh ``MockAgentRunner`` with strict mode enabled.
    """
    from claudekit.testing._mock_agent import MockAgentRunner

    return MockAgentRunner(strict=True)


@pytest.fixture
def mock_session_manager() -> Any:
    """Provide a :class:`~claudekit.testing.MockSessionManager` instance.

    Yields:
        A fresh ``MockSessionManager``.
    """
    from claudekit.testing._mock_session import MockSessionManager

    return MockSessionManager()


__all__ = [
    "mock_client",
    "mock_anthropic",
    "tracked_client",
    "mock_agent_runner",
    "mock_session_manager",
]

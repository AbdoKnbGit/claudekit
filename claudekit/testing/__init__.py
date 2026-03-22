"""claudekit.testing -- Zero-API testing utilities for claudekit applications.

Provides mock clients, assertion helpers, pytest fixtures, and response
recording/replay for testing Claude-powered applications without making
real API calls.

Two mocking approaches are supported:

1. **High-level MockClient** — Pattern-matching with ``construct()``-based
   responses. Quick to set up, no SDK validation runs.

2. **Realistic MockTransport** — Injects ``httpx.MockTransport`` into the
   real ``anthropic.Anthropic`` client so the **full SDK stack** runs:
   auth headers, retries, Pydantic validation, error mapping — with zero
   network calls.  This is the most realistic approach for production testing.

Modules
-------
_mock_client
    :class:`MockClient` -- high-level drop-in TrackedClient replacement.
_mock_transport
    :func:`create_mock_anthropic` -- realistic mock via httpx.MockTransport.
_mock_agent
    :class:`MockAgentRunner` -- mock for AgentRunner.
_mock_session
    :class:`MockSession`, :class:`MockSessionManager` -- session isolation.
_expect
    Assertion builders: ``contains``, ``matches``, ``tool_called``, etc.
_assertions
    :func:`assert_response`, :func:`assert_agent_result` -- batch evaluation.
_fixtures
    Pytest fixtures for common test scaffolding.
_recorder
    :class:`ResponseRecorder` -- record/replay API interactions.
"""

from __future__ import annotations

from claudekit.testing._mock_client import MockClient, MockClientUnexpectedCallError, MockStreamContext
from claudekit.testing._mock_transport import MockTransportHandler, create_mock_anthropic
from claudekit.testing._mock_agent import MockAgentRunner, MockAgentResult
from claudekit.testing._mock_session import MockSession, MockSessionManager
from claudekit.testing._assertions import assert_response, assert_agent_result
from claudekit.testing._recorder import ResponseRecorder
from claudekit.testing import _expect as expect

__all__ = [
    # High-level mock
    "MockClient",
    "MockClientUnexpectedCallError",
    "MockStreamContext",
    # Realistic transport mock
    "MockTransportHandler",
    "create_mock_anthropic",
    # Agent mock
    "MockAgentRunner",
    "MockAgentResult",
    # Session mock
    "MockSession",
    "MockSessionManager",
    # Assertions
    "assert_response",
    "assert_agent_result",
    "expect",
    # Recording
    "ResponseRecorder",
]

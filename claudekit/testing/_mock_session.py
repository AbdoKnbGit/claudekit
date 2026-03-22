"""Mock session and session manager for zero-API testing.

Provides :class:`MockSession` and :class:`MockSessionManager` for testing
code that uses :class:`~claudekit.sessions.SessionManager` without making
any API calls.

Example::

    from claudekit.testing import MockSessionManager
    from claudekit.sessions import SessionConfig

    manager = MockSessionManager()
    session = manager.create(SessionConfig(name="s1", model="claude-haiku-4-5"))
    session.mock_reply("hello", "Hi there!")
    assert session.run("hello") == "Hi there!"
"""

from __future__ import annotations

import logging
from typing import Any

from claudekit._defaults import DEFAULT_FAST_MODEL
from claudekit.client._session import SessionUsage

logger = logging.getLogger(__name__)


class MockSession:
    """A mock session that returns pre-configured responses.

    Supports pattern-based response matching, lifecycle state management,
    and usage tracking — without making any API calls.

    Args:
        name: Session name.
        model: Model identifier.
        config: Optional session config dict.
    """

    def __init__(self, name: str, model: str = DEFAULT_FAST_MODEL, config: Any = None) -> None:
        self._name = name
        self._model = model
        self._config = config
        self._usage = SessionUsage()
        self._state: str = "running"
        self._patterns: list[tuple[str, str]] = []
        self._default_reply: str | None = None
        self._calls: list[dict[str, Any]] = []
        self._turn_count: int = 0

    @property
    def name(self) -> str:
        """The session name."""
        return self._name

    @property
    def state(self) -> str:
        """Current lifecycle state."""
        return self._state

    @property
    def usage(self) -> SessionUsage:
        """The session's usage tracker."""
        return self._usage

    @property
    def call_count(self) -> int:
        """Number of calls made."""
        return len(self._calls)

    @property
    def calls(self) -> list[dict[str, Any]]:
        """All calls made to this session."""
        return list(self._calls)

    def mock_reply(self, pattern: str, reply: str) -> None:
        """Register a pattern → reply mapping.

        Args:
            pattern: Substring to match against the prompt.
            reply: Text to return when matched.
        """
        self._patterns.append((pattern, reply))

    def set_default_reply(self, reply: str) -> None:
        """Set a default reply for unmatched prompts."""
        self._default_reply = reply

    def run(self, prompt: str, **kwargs: Any) -> str:
        """Send a prompt and return a mock response.

        Args:
            prompt: The user message.
            **kwargs: Ignored (for API compatibility).

        Returns:
            The matching mock reply text.

        Raises:
            RuntimeError: If no pattern matches and no default is set.
        """
        from claudekit.errors import SessionPausedError, SessionTerminatedError

        if self._state == "paused":
            raise SessionPausedError(f"Session {self._name!r} is paused.")
        if self._state in ("finished", "error"):
            raise SessionTerminatedError(f"Session {self._name!r} is {self._state}.")

        self._calls.append({"prompt": prompt, **kwargs})
        self._turn_count += 1

        for pat, reply in reversed(self._patterns):
            if pat.lower() in prompt.lower():
                return reply

        if self._default_reply is not None:
            return self._default_reply

        raise RuntimeError(
            f"MockSession {self._name!r}: no reply registered for {prompt!r}\n"
            f"Registered: {[p for p, _ in self._patterns]}"
        )

    def pause(self) -> None:
        """Pause the mock session."""
        self._state = "paused"

    def resume(self) -> None:
        """Resume the mock session."""
        self._state = "running"

    def terminate(self) -> None:
        """Terminate the mock session."""
        self._state = "finished"

    def __repr__(self) -> str:
        return f"MockSession(name={self._name!r}, state={self._state!r})"


class MockSessionManager:
    """A mock session manager for zero-API testing of multi-session code.

    Creates :class:`MockSession` instances and tracks them by name.
    Provides the same interface as :class:`~claudekit.sessions.SessionManager`.

    Example::

        manager = MockSessionManager()
        s1 = manager.create(SessionConfig(name="s1", model="claude-haiku-4-5"))
        s2 = manager.create(SessionConfig(name="s2", model="claude-haiku-4-5"))
        s1.mock_reply("hello", "Hi from s1!")
        s2.mock_reply("hello", "Hi from s2!")
        assert s1.run("hello") != s2.run("hello")
    """

    def __init__(self) -> None:
        self._sessions: dict[str, MockSession] = {}

    def create(self, config: Any) -> MockSession:
        """Create a new mock session from a config.

        Args:
            config: A :class:`~claudekit.sessions.SessionConfig` or any
                object with ``name`` and ``model`` attributes.

        Returns:
            A new :class:`MockSession`.

        Raises:
            ValueError: If a session with the same name already exists and
                is still running.
        """
        name = getattr(config, "name", str(config))
        model = getattr(config, "model", DEFAULT_FAST_MODEL)

        if name in self._sessions and self._sessions[name].state == "running":
            raise ValueError(f"Session {name!r} already exists and is running.")

        session = MockSession(name=name, model=model, config=config)
        self._sessions[name] = session
        return session

    def get(self, name: str) -> MockSession | None:
        """Get a session by name."""
        return self._sessions.get(name)

    def all(self) -> list[MockSession]:
        """Get all sessions."""
        return list(self._sessions.values())

    def by_tag(self, tag: str) -> list[MockSession]:
        """Get sessions filtered by tag (reads config.tags if available)."""
        result = []
        for session in self._sessions.values():
            config = session._config
            tags = getattr(config, "tags", None) or []
            if tag in tags:
                result.append(session)
        return result

    def terminate(self, name: str) -> None:
        """Terminate a session by name."""
        session = self._sessions.get(name)
        if session:
            session.terminate()

    def terminate_all(self) -> None:
        """Terminate all sessions."""
        for session in self._sessions.values():
            session.terminate()

    def status(self) -> dict[str, str]:
        """Get state of all sessions."""
        return {name: s.state for name, s in self._sessions.items()}

    def broadcast_event(self, event: str, data: Any = None) -> None:
        """Broadcast an event to all running sessions (no-op in mock)."""
        logger.debug("MockSessionManager broadcast: %s", event)

    def __repr__(self) -> str:
        return f"MockSessionManager(sessions={list(self._sessions.keys())})"


__all__ = ["MockSession", "MockSessionManager"]

"""Managed session wrapping a :class:`~claudekit.client.TrackedClient`.

A :class:`Session` encapsulates its own :class:`SessionConfig`, maintains
lifecycle state, enforces cost budgets, and exposes a convenient ``run()``
helper alongside the standard ``messages.create()`` / ``messages.stream()``
proxies.
"""

from __future__ import annotations

import collections
import logging
import threading
import time
from typing import Any, Deque, Optional, Tuple

from claudekit.client._session import CallRecord, SessionUsage
from claudekit.errors import (
    ConfigurationError,
    SessionBudgetExceededError,
    SessionPausedError,
    SessionTerminatedError,
)
from claudekit.sessions._config import SessionConfig

logger = logging.getLogger(__name__)

# Valid lifecycle states
_VALID_STATES = frozenset({"running", "paused", "finished", "error"})


class _SessionMessages:
    """Proxy for ``messages.create()`` and ``messages.stream()`` scoped to a session.

    Injects the session's model, system prompt, and tools into every call and
    enforces lifecycle and budget constraints before forwarding to the
    underlying :class:`~claudekit.client.TrackedClient`.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, **kwargs: Any) -> Any:
        """Call ``messages.create()`` with session defaults applied.

        Args:
            **kwargs: Arguments forwarded to the underlying tracked client.
                ``model``, ``system``, and ``tools`` are injected from session
                config if not explicitly provided.

        Returns:
            The API response.

        Raises:
            SessionPausedError: If the session is paused.
            SessionTerminatedError: If the session is finished or in error state.
            SessionBudgetExceededError: If the cost budget has been reached.
        """
        self._session._check_can_call()
        kwargs = self._session._apply_defaults(kwargs)
        response = self._session._client.messages.create(**kwargs)
        self._session._after_call()
        return response

    def stream(self, **kwargs: Any) -> Any:
        """Call ``messages.stream()`` with session defaults applied.

        Args:
            **kwargs: Arguments forwarded to the underlying tracked client.

        Returns:
            A stream context manager.

        Raises:
            SessionPausedError: If the session is paused.
            SessionTerminatedError: If the session is finished or in error state.
            SessionBudgetExceededError: If the cost budget has been reached.
        """
        self._session._check_can_call()
        kwargs = self._session._apply_defaults(kwargs)
        stream = self._session._client.messages.stream(**kwargs)
        # Note: cost check happens lazily -- we can't know cost before stream
        # completes.  We wrap to check after.
        session = self._session

        class _PostCallStreamWrapper:
            """Wrapper that fires the session's after-call hook on exit."""

            def __init__(self, inner: Any) -> None:
                self._inner = inner

            def __enter__(self) -> Any:
                self._stream = self._inner.__enter__()
                return self._stream

            def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Any:
                result = self._inner.__exit__(exc_type, exc_val, exc_tb)
                if exc_type is None:
                    session._after_call()
                return result

            def __getattr__(self, name: str) -> Any:
                return getattr(self._inner, name)

        return _PostCallStreamWrapper(stream)


class Session:
    """A managed session with lifecycle, budget enforcement, and event support.

    Sessions are created via :meth:`SessionManager.create` and should not
    normally be instantiated directly.

    Parameters
    ----------
    config:
        The :class:`SessionConfig` defining this session's behaviour.
    client:
        A :class:`~claudekit.client.TrackedClient` to use for API calls.
        The session records usage into its own :class:`SessionUsage`.

    Attributes
    ----------
    messages:
        A proxy object with ``create()`` and ``stream()`` methods that
        automatically apply session defaults (model, system, tools).
    """

    def __init__(self, config: SessionConfig, client: Any) -> None:
        self._config = config
        self._client = client
        self._usage = SessionUsage()
        self._state: str = "running"
        self._lock = threading.Lock()
        self._turn_count: int = 0
        self._cost_warning_fired: bool = False
        self._event_queue: Deque[Tuple[str, Any]] = collections.deque(maxlen=1000)
        self._created_at: float = time.time()

        # Build a tracked client scoped to this session's usage
        self._client = client.with_options()
        # Point the new client's usage at our session-specific tracker
        self._client._usage = self._usage
        self._client._messages = type(self._client._messages)(
            self._client._messages._messages, self._usage
        )

        self.messages = _SessionMessages(self)

        logger.info("Session %r created (model=%s)", config.name, config.model)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        """The unique name of this session."""
        return self._config.name

    @property
    def state(self) -> str:
        """Current lifecycle state: ``'running'``, ``'paused'``, ``'finished'``, or ``'error'``."""
        with self._lock:
            return self._state

    @property
    def usage(self) -> SessionUsage:
        """The :class:`SessionUsage` tracker for this session."""
        return self._usage

    @property
    def config(self) -> SessionConfig:
        """The :class:`SessionConfig` that governs this session."""
        return self._config

    @property
    def turn_count(self) -> int:
        """Number of completed conversation turns."""
        with self._lock:
            return self._turn_count

    @property
    def event_queue(self) -> Deque[Tuple[str, Any]]:
        """The deque of broadcast events received by this session."""
        return self._event_queue

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def pause(self) -> None:
        """Pause the session, preventing further API calls.

        Raises
        ------
        SessionTerminatedError
            If the session is already finished or in error state.
        """
        with self._lock:
            if self._state in ("finished", "error"):
                raise SessionTerminatedError(
                    f"Cannot pause session {self.name!r}: state is {self._state!r}.",
                    context={"session": self.name, "state": self._state},
                )
            self._state = "paused"
        logger.info("Session %r paused", self.name)

    def resume(self) -> None:
        """Resume a paused session.

        Raises
        ------
        SessionTerminatedError
            If the session is finished or in error state.
        """
        with self._lock:
            if self._state in ("finished", "error"):
                raise SessionTerminatedError(
                    f"Cannot resume session {self.name!r}: state is {self._state!r}.",
                    context={"session": self.name, "state": self._state},
                )
            self._state = "running"
        logger.info("Session %r resumed", self.name)

    def terminate(self) -> None:
        """Terminate the session.  No further operations are possible."""
        with self._lock:
            self._state = "finished"
        logger.info("Session %r terminated", self.name)

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def run(self, prompt: str) -> str:
        """Send a single user prompt and return the assistant's text response.

        This is a convenience wrapper around ``messages.create()`` that
        constructs the message list and extracts the text reply.

        Args:
            prompt: The user message content.

        Returns:
            The assistant's text response.

        Raises:
            SessionPausedError: If the session is paused.
            SessionTerminatedError: If the session is terminated.
            SessionBudgetExceededError: If the budget has been exceeded.
        """
        messages = [{"role": "user", "content": prompt}]
        response = self.messages.create(
            messages=messages,
            max_tokens=self._config.max_tokens or 4096,
        )
        # Extract text from response content blocks
        text_parts: list[str] = []
        for block in response.content:
            if getattr(block, "type", None) == "text":
                text_parts.append(block.text)
        return "\n".join(text_parts)

    # ------------------------------------------------------------------
    # Broadcast support
    # ------------------------------------------------------------------

    def receive_event(self, event: str, data: Any) -> None:
        """Enqueue a broadcast event for this session.

        Args:
            event: Event name / type.
            data: Arbitrary event payload.
        """
        if self._config.ignore_broadcasts:
            return
        self._event_queue.append((event, data))
        logger.debug("Session %r received event %r", self.name, event)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_can_call(self) -> None:
        """Verify that the session is in a state that permits API calls.

        Raises:
            SessionPausedError: If paused.
            SessionTerminatedError: If finished or error.
            SessionBudgetExceededError: If cost budget exceeded.
        """
        with self._lock:
            if self._state == "paused":
                raise SessionPausedError(
                    f"Session {self.name!r} is paused.",
                    context={"session": self.name},
                )
            if self._state in ("finished", "error"):
                raise SessionTerminatedError(
                    f"Session {self.name!r} is {self._state}.",
                    context={"session": self.name, "state": self._state},
                )

        # Budget check (before the call)
        if self._config.max_cost_usd is not None:
            current_cost = self._usage.estimated_cost
            if current_cost >= self._config.max_cost_usd:
                with self._lock:
                    self._state = "error"
                raise SessionBudgetExceededError(
                    f"Session {self.name!r} budget exhausted: "
                    f"${current_cost:.4f} >= ${self._config.max_cost_usd:.4f}.",
                    context={
                        "session": self.name,
                        "current_cost": current_cost,
                        "limit": self._config.max_cost_usd,
                    },
                )

        # Turn limit check
        if self._config.max_turns is not None:
            with self._lock:
                if self._turn_count >= self._config.max_turns:
                    self._state = "finished"
                    raise SessionTerminatedError(
                        f"Session {self.name!r} reached max turns ({self._config.max_turns}).",
                        context={
                            "session": self.name,
                            "turn_count": self._turn_count,
                            "max_turns": self._config.max_turns,
                        },
                    )

    def _apply_defaults(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Inject session-level defaults into API call kwargs.

        Args:
            kwargs: The keyword arguments dict (mutated in place and returned).

        Returns:
            The updated kwargs dict.
        """
        kwargs.setdefault("model", self._config.model)
        if self._config.system is not None and "system" not in kwargs:
            kwargs["system"] = self._config.system
        if self._config.tools is not None and "tools" not in kwargs:
            kwargs["tools"] = self._config.tools
        return kwargs

    def _after_call(self) -> None:
        """Post-call bookkeeping: increment turn count, check cost warning."""
        with self._lock:
            self._turn_count += 1

        # Cost warning (fire exactly once at 80%)
        if (
            self._config.max_cost_usd is not None
            and not self._cost_warning_fired
        ):
            current_cost = self._usage.estimated_cost
            threshold = self._config.max_cost_usd * 0.8
            if current_cost >= threshold:
                self._cost_warning_fired = True
                logger.warning(
                    "Session %r cost warning: $%.4f / $%.4f (%.0f%%)",
                    self.name,
                    current_cost,
                    self._config.max_cost_usd,
                    (current_cost / self._config.max_cost_usd) * 100,
                )
                if self._config.on_cost_warning is not None:
                    try:
                        self._config.on_cost_warning(
                            self.name, current_cost, self._config.max_cost_usd
                        )
                    except (AttributeError, TypeError, ValueError):
                        logger.exception(
                            "on_cost_warning callback failed for session %r",
                            self.name,
                        )

    def _set_error(self, error: Exception) -> None:
        """Transition to the error state and invoke the on_error callback.

        Args:
            error: The exception that caused the error.
        """
        with self._lock:
            self._state = "error"
        logger.error("Session %r entered error state: %s", self.name, error)
        if self._config.on_error is not None:
            try:
                self._config.on_error(self.name, error)
            except (AttributeError, TypeError, ValueError):
                logger.exception(
                    "on_error callback failed for session %r", self.name
                )

    def __repr__(self) -> str:
        return (
            f"Session(name={self.name!r}, state={self.state!r}, "
            f"model={self._config.model!r}, turns={self.turn_count})"
        )


__all__ = ["Session"]

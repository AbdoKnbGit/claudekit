"""Session lifecycle manager.

:class:`SessionManager` creates, tracks, and controls multiple
:class:`Session` instances.  It provides tag-based filtering, status
reporting, broadcast events, and aggregated usage via
:class:`MultiSessionUsage`.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional

from claudekit.errors import (
    ConfigurationError,
    SessionNameConflictError,
    SessionTerminatedError,
)
from claudekit.sessions._aggregator import MultiSessionUsage
from claudekit.sessions._config import SessionConfig
from claudekit.sessions._session import Session

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages the lifecycle of multiple :class:`Session` instances.

    Parameters
    ----------
    client:
        A :class:`~claudekit.client.TrackedClient` used to create sessions.
        Each session gets its own usage-tracked clone of this client.

    Example
    -------
    ::

        from claudekit.client import TrackedClient
        from claudekit.sessions import SessionManager, SessionConfig

        client = TrackedClient()
        manager = SessionManager(client)

        config = SessionConfig(name="qa", model="claude-haiku-4-5", tags=["qa"])
        session = manager.create(config)
        answer = session.run("What is 2+2?")

        print(manager.status())
        manager.terminate_all()
    """

    def __init__(self, client: Any) -> None:
        self._client = client
        self._sessions: Dict[str, Session] = {}
        self._sessions_list: List[Session] = []  # Ordered insertion list
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Session CRUD
    # ------------------------------------------------------------------

    def create(self, config: SessionConfig) -> Session:
        """Create and register a new session.

        Args:
            config: The :class:`SessionConfig` for the new session.

        Returns:
            The newly created :class:`Session`.

        Raises:
            SessionNameConflictError: If a session with the same name exists
                and is not terminated.
        """
        with self._lock:
            existing = self._sessions.get(config.name)
            if existing is not None and existing.state not in ("finished", "error"):
                raise SessionNameConflictError(
                    f"A session named {config.name!r} already exists "
                    f"(state={existing.state!r}).",
                    context={"session": config.name, "state": existing.state},
                )

            session = Session(config, self._client)
            self._sessions[config.name] = session
            self._sessions_list.append(session)

        logger.info("SessionManager: created session %r", config.name)
        return session

    def get(self, name: str) -> Optional[Session]:
        """Look up a session by name.

        Args:
            name: The session name.

        Returns:
            The :class:`Session` if found, ``None`` otherwise.
        """
        with self._lock:
            return self._sessions.get(name)

    def all(self) -> List[Session]:
        """Return all sessions in creation order.

        Returns:
            List of all managed sessions.
        """
        with self._lock:
            return list(self._sessions_list)

    def by_tag(self, tag: str) -> List[Session]:
        """Return sessions that have the given tag.

        Args:
            tag: The tag to filter by.

        Returns:
            List of sessions whose config includes this tag.
        """
        with self._lock:
            return [
                s
                for s in self._sessions_list
                if s.config.tags and tag in s.config.tags
            ]

    # ------------------------------------------------------------------
    # Lifecycle control
    # ------------------------------------------------------------------

    def pause(self, name: str) -> None:
        """Pause the named session.

        Args:
            name: The session name.

        Raises:
            KeyError: If no session with the given name exists.
            SessionTerminatedError: If the session is already terminated.
        """
        session = self._require(name)
        session.pause()

    def resume(self, name: str) -> None:
        """Resume the named session.

        Args:
            name: The session name.

        Raises:
            KeyError: If no session with the given name exists.
            SessionTerminatedError: If the session is already terminated.
        """
        session = self._require(name)
        session.resume()

    def terminate(self, name: str) -> None:
        """Terminate the named session.

        Args:
            name: The session name.

        Raises:
            KeyError: If no session with the given name exists.
        """
        session = self._require(name)
        session.terminate()

    def terminate_all(self) -> None:
        """Terminate every managed session.

        Sessions already in ``"finished"`` or ``"error"`` state are skipped.
        """
        with self._lock:
            sessions = list(self._sessions_list)
        for session in sessions:
            if session.state not in ("finished", "error"):
                try:
                    session.terminate()
                except (AttributeError, TypeError, ValueError, RuntimeError):
                    logger.debug(
                        "Ignoring error while terminating session %r",
                        session.name,
                        exc_info=True,
                    )
        logger.info("SessionManager: terminated all sessions")

    # ------------------------------------------------------------------
    # Status & usage
    # ------------------------------------------------------------------

    def status(self) -> Dict[str, str]:
        """Return a mapping of session names to their current state.

        Returns:
            Dict mapping each session name to its lifecycle state string.
        """
        with self._lock:
            return {s.name: s.state for s in self._sessions_list}

    @property
    def usage(self) -> MultiSessionUsage:
        """Aggregated usage view across all sessions.

        Returns:
            A :class:`MultiSessionUsage` instance covering all managed
            sessions.
        """
        with self._lock:
            return MultiSessionUsage(list(self._sessions_list))

    # ------------------------------------------------------------------
    # Broadcasting
    # ------------------------------------------------------------------

    def broadcast_event(self, event: str, data: Any = None) -> None:
        """Broadcast an event to all eligible sessions.

        Events are delivered best-effort: sessions in ``"finished"`` or
        ``"error"`` state are skipped, and exceptions from individual
        sessions are caught and logged.

        Args:
            event: Event name / type.
            data: Arbitrary payload.
        """
        with self._lock:
            targets = list(self._sessions_list)

        delivered = 0
        for session in targets:
            if session.state in ("finished", "error"):
                continue
            try:
                session.receive_event(event, data)
                delivered += 1
            except (AttributeError, TypeError, ValueError, RuntimeError):
                logger.debug(
                    "Failed to deliver event %r to session %r",
                    event,
                    session.name,
                    exc_info=True,
                )

        logger.debug(
            "Broadcast event %r delivered to %d/%d sessions",
            event,
            delivered,
            len(targets),
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require(self, name: str) -> Session:
        """Look up a session or raise :class:`KeyError`.

        Args:
            name: The session name.

        Returns:
            The session.

        Raises:
            KeyError: If no session with the given name exists.
        """
        with self._lock:
            session = self._sessions.get(name)
        if session is None:
            raise KeyError(f"No session named {name!r}")
        return session

    def __repr__(self) -> str:
        with self._lock:
            count = len(self._sessions_list)
        return f"SessionManager(sessions={count})"


__all__ = ["SessionManager"]

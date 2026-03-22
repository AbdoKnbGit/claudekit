"""claudekit.sessions -- Managed session lifecycle and multi-session usage.

This module provides:

- :class:`SessionConfig` -- declarative session configuration.
- :class:`Session` -- a managed session wrapping a tracked client.
- :class:`SessionManager` -- lifecycle management for multiple sessions.
- :class:`MultiSessionUsage` -- aggregated usage across sessions.
"""

from __future__ import annotations

from claudekit.sessions._aggregator import MultiSessionUsage
from claudekit.sessions._config import SessionConfig
from claudekit.sessions._manager import SessionManager
from claudekit.sessions._session import Session

__all__ = [
    "MultiSessionUsage",
    "Session",
    "SessionConfig",
    "SessionManager",
]

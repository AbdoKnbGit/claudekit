"""Multi-session usage aggregation.

:class:`MultiSessionUsage` provides a zero-cost aggregated view across
multiple :class:`Session` instances without copying or duplicating the
underlying :class:`~claudekit.client._session.SessionUsage` data.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict, List

if TYPE_CHECKING:
    from claudekit.client._session import SessionUsage
    from claudekit.sessions._session import Session

logger = logging.getLogger(__name__)


class MultiSessionUsage:
    """Zero-cost aggregated usage view across multiple sessions.

    This class does **not** copy usage data.  Instead it holds references to
    live :class:`Session` objects and computes aggregates on demand.

    Parameters
    ----------
    sessions:
        The list of sessions to aggregate over.  The list is referenced
        (not copied), so newly created sessions will appear in subsequent
        queries only if the caller's list is updated.
    """

    def __init__(self, sessions: List[Session]) -> None:
        self._sessions = sessions

    @property
    def total_cost(self) -> float:
        """Total estimated cost across all sessions in USD."""
        return sum(s.usage.estimated_cost for s in self._sessions)

    def by_session(self) -> Dict[str, SessionUsage]:
        """Map each session name to its :class:`SessionUsage`.

        Returns:
            Dict mapping session names to their usage trackers.
        """
        return {s.name: s.usage for s in self._sessions}

    def most_expensive(self) -> str:
        """Return the name of the session with the highest cost.

        Returns:
            Session name, or an empty string if no sessions exist.
        """
        if not self._sessions:
            return ""
        return max(self._sessions, key=lambda s: s.usage.estimated_cost).name

    def summary(self) -> str:
        """Human-readable multi-session usage summary.

        Returns:
            Formatted string with per-session cost breakdown and totals.
        """
        if not self._sessions:
            return "No sessions."

        lines: list[str] = ["Multi-Session Usage Summary"]
        lines.append(f"  Sessions: {len(self._sessions)}")
        lines.append(f"  Total cost: ${self.total_cost:.6f}")

        if self._sessions:
            lines.append("  By session:")
            for session in sorted(
                self._sessions,
                key=lambda s: s.usage.estimated_cost,
                reverse=True,
            ):
                cost = session.usage.estimated_cost
                calls = session.usage.call_count
                lines.append(
                    f"    {session.name}: {calls} calls, ${cost:.6f} "
                    f"({session.state})"
                )

            most = self.most_expensive()
            if most:
                lines.append(f"  Most expensive: {most}")

        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"MultiSessionUsage(sessions={len(self._sessions)}, "
            f"total_cost=${self.total_cost:.6f})"
        )


__all__ = ["MultiSessionUsage"]

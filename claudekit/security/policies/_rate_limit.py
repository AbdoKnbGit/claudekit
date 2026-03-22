"""Rate-limiting policy with sliding-window enforcement.

:class:`RateLimitPolicy` enforces per-user request-rate limits using a
sliding-window algorithm.  It ships with an in-memory backend and
an :class:`AbstractRateLimitBackend` interface for external stores.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from typing import Any, Deque, Dict, List, Optional

from claudekit.errors._base import RateLimitError
from claudekit.security._context import SecurityContext
from claudekit.security._policy import Policy

logger = logging.getLogger("claudekit.security.rate_limit")

# =========================================================================== #
# Abstract backend
# =========================================================================== #


class AbstractRateLimitBackend(ABC):
    """Interface for external rate-limit storage.

    Implement this to back rate-limit state with Redis, Memcached, or
    another shared store.
    """

    @abstractmethod
    def record_request(self, user_id: str, timestamp: float) -> None:
        """Record that a request was made by *user_id* at *timestamp*."""
        ...

    @abstractmethod
    def count_requests(
        self, user_id: str, since_timestamp: float
    ) -> int:
        """Count requests by *user_id* since *since_timestamp*."""
        ...

    @abstractmethod
    def clear(self, user_id: Optional[str] = None) -> None:
        """Clear request data.  If *user_id* is ``None``, clear everything."""
        ...


# =========================================================================== #
# In-memory sliding-window backend
# =========================================================================== #


class InMemoryRateLimitBackend(AbstractRateLimitBackend):
    """In-memory sliding-window rate-limit backend.

    Timestamps are stored in per-user deques and expired entries are pruned
    lazily on each access.

    Not suitable for production multi-process deployments -- use a shared
    store like Redis instead.
    """

    def __init__(self) -> None:
        self._store: Dict[str, Deque[float]] = defaultdict(deque)

    def record_request(self, user_id: str, timestamp: float) -> None:
        self._store[user_id].append(timestamp)

    def count_requests(self, user_id: str, since_timestamp: float) -> int:
        dq = self._store.get(user_id)
        if dq is None:
            return 0
        # Prune expired entries from the left
        while dq and dq[0] < since_timestamp:
            dq.popleft()
        return len(dq)

    def clear(self, user_id: Optional[str] = None) -> None:
        if user_id is None:
            self._store.clear()
        else:
            self._store.pop(user_id, None)


# =========================================================================== #
# Policy class
# =========================================================================== #


class RateLimitPolicy(Policy):
    """Enforce per-user request rate limits with sliding windows.

    Parameters
    ----------
    requests_per_minute:
        Maximum requests per minute per user.  ``None`` for no limit.
    requests_per_hour:
        Maximum requests per hour per user.  ``None`` for no limit.
    requests_per_day:
        Maximum requests per day per user.  ``None`` for no limit.
    backend:
        Rate-limit storage backend.  Defaults to
        :class:`InMemoryRateLimitBackend`.
    """

    name: str = "rate_limit"

    def __init__(
        self,
        requests_per_minute: Optional[int] = None,
        requests_per_hour: Optional[int] = None,
        requests_per_day: Optional[int] = None,
        backend: Optional[AbstractRateLimitBackend] = None,
    ) -> None:
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.requests_per_day = requests_per_day
        self.backend: AbstractRateLimitBackend = (
            backend or InMemoryRateLimitBackend()
        )

    # ------------------------------------------------------------------ #
    # Hooks
    # ------------------------------------------------------------------ #

    def check_request(
        self,
        messages: List[Dict[str, Any]],
        context: SecurityContext,
    ) -> None:
        """Check rate limits and record the request if allowed."""
        user_id = context.user_id or "__anonymous__"
        now = time.time()

        # Check per-minute limit
        if self.requests_per_minute is not None:
            count = self.backend.count_requests(user_id, now - 60)
            if count >= self.requests_per_minute:
                raise RateLimitError(
                    f"Rate limit exceeded for user {user_id!r}: "
                    f"{count}/{self.requests_per_minute} requests per minute",
                    context={
                        "user_id": user_id,
                        "window": "1m",
                        "count": count,
                        "limit": self.requests_per_minute,
                        "request_id": context.request_id,
                    },
                    recovery_hint="Wait before retrying.",
                )

        # Check per-hour limit
        if self.requests_per_hour is not None:
            count = self.backend.count_requests(user_id, now - 3600)
            if count >= self.requests_per_hour:
                raise RateLimitError(
                    f"Rate limit exceeded for user {user_id!r}: "
                    f"{count}/{self.requests_per_hour} requests per hour",
                    context={
                        "user_id": user_id,
                        "window": "1h",
                        "count": count,
                        "limit": self.requests_per_hour,
                        "request_id": context.request_id,
                    },
                    recovery_hint="Wait before retrying.",
                )

        # Check per-day limit
        if self.requests_per_day is not None:
            count = self.backend.count_requests(user_id, now - 86400)
            if count >= self.requests_per_day:
                raise RateLimitError(
                    f"Rate limit exceeded for user {user_id!r}: "
                    f"{count}/{self.requests_per_day} requests per day",
                    context={
                        "user_id": user_id,
                        "window": "24h",
                        "count": count,
                        "limit": self.requests_per_day,
                        "request_id": context.request_id,
                    },
                    recovery_hint="Wait before retrying.",
                )

        # All checks passed: record the request
        self.backend.record_request(user_id, now)
        logger.debug(
            "Rate limit check passed for %s (request_id=%s)",
            user_id,
            context.request_id,
        )


__all__ = [
    "AbstractRateLimitBackend",
    "InMemoryRateLimitBackend",
    "RateLimitPolicy",
]

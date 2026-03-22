"""Per-user budget enforcement policy.

:class:`BudgetPolicy` tracks spend and token usage on a per-user basis
within configurable time windows.  It supports an in-memory backend by
default and an :class:`AbstractBudgetBackend` interface for plugging in
external stores (Redis, PostgreSQL, etc.).
"""

from __future__ import annotations

import logging
import time
import warnings
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from claudekit.errors._base import BudgetExceededError, TokenLimitError
from claudekit.security._context import SecurityContext
from claudekit.security._policy import Policy

logger = logging.getLogger("claudekit.security.budget")

# =========================================================================== #
# Window parsing
# =========================================================================== #

_WINDOW_SECONDS: Dict[str, int] = {
    "1m": 60,
    "1h": 3600,
    "24h": 86400,
    "7d": 604800,
    "30d": 2592000,
}


def _parse_window(window: str) -> int:
    """Convert a window string to seconds."""
    seconds = _WINDOW_SECONDS.get(window)
    if seconds is None:
        raise ValueError(
            f"Invalid window {window!r}. Valid values: {list(_WINDOW_SECONDS)}"
        )
    return seconds


# =========================================================================== #
# Usage record
# =========================================================================== #


@dataclass
class UsageRecord:
    """A single usage event."""

    timestamp: float
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0


# =========================================================================== #
# Abstract backend
# =========================================================================== #


class AbstractBudgetBackend(ABC):
    """Interface for external budget-tracking storage.

    Subclass this to integrate with Redis, PostgreSQL, or any other
    persistent store for cross-process / cross-instance budget tracking.
    """

    @abstractmethod
    def record_usage(self, user_id: str, record: UsageRecord) -> None:
        """Persist a usage event."""
        ...

    @abstractmethod
    def get_usage(
        self, user_id: str, since_timestamp: float
    ) -> List[UsageRecord]:
        """Retrieve usage records for *user_id* since *since_timestamp*."""
        ...

    @abstractmethod
    def clear(self, user_id: Optional[str] = None) -> None:
        """Clear usage data.  If *user_id* is ``None``, clear everything."""
        ...


# =========================================================================== #
# In-memory backend
# =========================================================================== #


class InMemoryBudgetBackend(AbstractBudgetBackend):
    """Simple in-memory backend for development and testing.

    Not suitable for production multi-process deployments -- use a shared
    store like Redis instead.
    """

    def __init__(self) -> None:
        self._store: Dict[str, List[UsageRecord]] = defaultdict(list)

    def record_usage(self, user_id: str, record: UsageRecord) -> None:
        self._store[user_id].append(record)

    def get_usage(
        self, user_id: str, since_timestamp: float
    ) -> List[UsageRecord]:
        return [
            r for r in self._store.get(user_id, []) if r.timestamp >= since_timestamp
        ]

    def clear(self, user_id: Optional[str] = None) -> None:
        if user_id is None:
            self._store.clear()
        else:
            self._store.pop(user_id, None)


# =========================================================================== #
# Budget Policy
# =========================================================================== #


class BudgetPolicy(Policy):
    """Enforce per-user cost and token budgets within a time window.

    Parameters
    ----------
    max_cost_usd:
        Maximum cumulative cost in USD per user within *window*.
        ``None`` means unlimited.
    max_input_tokens:
        Maximum cumulative input tokens per user within *window*.
        ``None`` means unlimited.
    max_output_tokens:
        Maximum cumulative output tokens per user within *window*.
        ``None`` means unlimited.
    window:
        Time window: ``"1m"``, ``"1h"``, ``"24h"``, ``"7d"``, or ``"30d"``.
    backend:
        Budget storage backend.  Defaults to :class:`InMemoryBudgetBackend`.
    warn_at_percent:
        When usage reaches this percentage of any limit, the
        *on_warning* callback is fired.  ``None`` disables warnings.
    on_warning:
        Callback invoked when the warning threshold is reached.  Receives
        a dict with ``user_id``, ``metric`` (e.g. ``"cost_usd"``),
        ``current``, ``limit``, and ``percent``.
    """

    name: str = "budget"

    def __init__(
        self,
        max_cost_usd: Optional[float] = None,
        max_input_tokens: Optional[int] = None,
        max_output_tokens: Optional[int] = None,
        window: str = "24h",
        backend: Optional[AbstractBudgetBackend] = None,
        warn_at_percent: Optional[float] = 80.0,
        on_warning: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        self.max_cost_usd = max_cost_usd
        self.max_input_tokens = max_input_tokens
        self.max_output_tokens = max_output_tokens
        self.window_str = window
        self.window_seconds = _parse_window(window)
        self.backend: AbstractBudgetBackend = backend or InMemoryBudgetBackend()
        self.warn_at_percent = warn_at_percent
        self.on_warning = on_warning

    # ------------------------------------------------------------------ #
    # Hooks
    # ------------------------------------------------------------------ #

    def check_request(
        self,
        messages: List[Dict[str, Any]],
        context: SecurityContext,
    ) -> None:
        """Verify the user has not exceeded their budget before sending."""
        user_id = context.user_id or "__anonymous__"
        since = time.time() - self.window_seconds
        records = self.backend.get_usage(user_id, since)

        total_cost = sum(r.cost_usd for r in records)
        total_input = sum(r.input_tokens for r in records)
        total_output = sum(r.output_tokens for r in records)

        # Check cost
        if self.max_cost_usd is not None:
            self._check_limit(
                user_id,
                "cost_usd",
                total_cost,
                self.max_cost_usd,
                context,
            )

        # Check input tokens
        if self.max_input_tokens is not None:
            self._check_limit(
                user_id,
                "input_tokens",
                total_input,
                float(self.max_input_tokens),
                context,
            )

        # Check output tokens
        if self.max_output_tokens is not None:
            self._check_limit(
                user_id,
                "output_tokens",
                total_output,
                float(self.max_output_tokens),
                context,
            )

    def check_response(
        self,
        response: Any,
        context: SecurityContext,
    ) -> Any:
        """Record usage from the response and pass it through."""
        user_id = context.user_id or "__anonymous__"
        usage = self._extract_usage(response)
        if usage:
            self.backend.record_usage(user_id, usage)
            logger.debug(
                "Recorded usage for %s: cost=$%.6f, in=%d, out=%d",
                user_id,
                usage.cost_usd,
                usage.input_tokens,
                usage.output_tokens,
            )
        return response

    # ------------------------------------------------------------------ #
    # Public helpers
    # ------------------------------------------------------------------ #

    def record_usage(
        self,
        user_id: str,
        cost_usd: float = 0.0,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> None:
        """Manually record a usage event (useful when cost is known externally).

        Parameters
        ----------
        user_id:
            The user to attribute the usage to.
        cost_usd:
            Dollar cost of the request.
        input_tokens:
            Number of input tokens consumed.
        output_tokens:
            Number of output tokens generated.
        """
        record = UsageRecord(
            timestamp=time.time(),
            cost_usd=cost_usd,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        self.backend.record_usage(user_id, record)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _check_limit(
        self,
        user_id: str,
        metric: str,
        current: float,
        limit: float,
        context: SecurityContext,
    ) -> None:
        """Check a single limit and fire warning/error as needed."""
        if limit <= 0:
            return

        percent = (current / limit) * 100.0

        # Warning callback
        if (
            self.warn_at_percent is not None
            and percent >= self.warn_at_percent
            and percent < 100.0
        ):
            info = {
                "user_id": user_id,
                "metric": metric,
                "current": current,
                "limit": limit,
                "percent": percent,
            }
            logger.warning(
                "Budget warning for %s: %s at %.1f%% (%s / %s)",
                user_id,
                metric,
                percent,
                current,
                limit,
            )
            if self.on_warning:
                self.on_warning(info)

        # Hard limit
        if current >= limit:
            if metric == "cost_usd":
                raise BudgetExceededError(
                    f"User {user_id!r} exceeded cost budget: "
                    f"${current:.4f} >= ${limit:.4f} (window={self.window_str})",
                    context={
                        "user_id": user_id,
                        "metric": metric,
                        "current": current,
                        "limit": limit,
                        "window": self.window_str,
                        "request_id": context.request_id,
                    },
                )
            else:
                raise TokenLimitError(
                    f"User {user_id!r} exceeded {metric} limit: "
                    f"{int(current)} >= {int(limit)} (window={self.window_str})",
                    context={
                        "user_id": user_id,
                        "metric": metric,
                        "current": int(current),
                        "limit": int(limit),
                        "window": self.window_str,
                        "request_id": context.request_id,
                    },
                )

    def _extract_usage(self, response: Any) -> Optional[UsageRecord]:
        """Try to extract token usage from a response object."""
        usage = None

        # Dict response
        if isinstance(response, dict):
            usage = response.get("usage")
        else:
            usage = getattr(response, "usage", None)

        if usage is None:
            return None

        if isinstance(usage, dict):
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
        else:
            input_tokens = getattr(usage, "input_tokens", 0)
            output_tokens = getattr(usage, "output_tokens", 0)

        # Rough cost estimation based on Claude pricing
        # These are approximate and should be overridden via record_usage
        # for accurate billing.
        cost_usd = (input_tokens * 0.000003) + (output_tokens * 0.000015)

        return UsageRecord(
            timestamp=time.time(),
            cost_usd=cost_usd,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )


__all__ = [
    "AbstractBudgetBackend",
    "BudgetPolicy",
    "InMemoryBudgetBackend",
    "UsageRecord",
]

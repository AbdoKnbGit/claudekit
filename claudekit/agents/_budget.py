"""BudgetGuard -- enforce cost and turn limits around agent runs.

The guard wraps an :class:`~claudekit.agents.AgentRunner` and checks limits
after each run, emitting warnings as thresholds are approached and raising
:class:`~claudekit.errors.BudgetExceededError` when hard limits are hit.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

from claudekit.agents._runner import AgentResult, AgentRunner

logger = logging.getLogger(__name__)


class BudgetGuard:
    """Wraps an :class:`AgentRunner` with cost and turn enforcement.

    The guard maintains running totals across multiple :meth:`run` invocations
    and fires callbacks as warning and hard-limit thresholds are crossed.

    Parameters
    ----------
    runner:
        The :class:`AgentRunner` to protect.
    max_cost_usd:
        Hard ceiling on cumulative cost in USD.  ``None`` = unlimited.
    max_turns:
        Hard ceiling on cumulative turns.  ``None`` = unlimited.
    warn_at_cost_usd:
        Cost at which to fire the *on_warn* callback.  ``None`` = no warning.
    warn_at_turns:
        Turn count at which to fire the *on_warn* callback.  ``None`` = no warning.
    on_warn:
        Called with ``(metric: str, current: float, limit: float)`` when a
        warning threshold is crossed.  Defaults to :func:`logging.warning`.
    on_limit:
        Called with ``(metric: str, current: float, limit: float)`` just before
        a :class:`~claudekit.errors.BudgetExceededError` is raised.  Useful for
        cleanup.  Defaults to ``None`` (no-op).
    on_complete:
        Called with the :class:`AgentResult` after a successful run.
        Defaults to ``None`` (no-op).

    Examples
    --------
    >>> from claudekit.agents import Agent, AgentRunner, BudgetGuard
    >>> agent = Agent(name="worker", system="Do tasks.")
    >>> guard = BudgetGuard(AgentRunner(agent), max_cost_usd=1.0, warn_at_cost_usd=0.8)
    >>> result = guard.run("Summarise this report.")
    """

    def __init__(
        self,
        runner: AgentRunner,
        *,
        max_cost_usd: Optional[float] = None,
        max_turns: Optional[int] = None,
        warn_at_cost_usd: Optional[float] = None,
        warn_at_turns: Optional[int] = None,
        on_warn: Optional[Callable[[str, float, float], None]] = None,
        on_limit: Optional[Callable[[str, float, float], None]] = None,
        on_complete: Optional[Callable[[AgentResult], None]] = None,
    ) -> None:
        self._runner = runner
        self._max_cost_usd = max_cost_usd
        self._max_turns = max_turns
        self._warn_at_cost_usd = warn_at_cost_usd
        self._warn_at_turns = warn_at_turns
        self._on_warn = on_warn or self._default_warn
        self._on_limit = on_limit
        self._on_complete = on_complete

        # Running totals
        self._total_cost: float = 0.0
        self._total_turns: int = 0
        self._run_count: int = 0

        # Track whether warnings have already fired (fire only once)
        self._cost_warned: bool = False
        self._turns_warned: bool = False

        logger.debug(
            "BudgetGuard initialised (max_cost=$%s, max_turns=%s, "
            "warn_cost=$%s, warn_turns=%s)",
            max_cost_usd,
            max_turns,
            warn_at_cost_usd,
            warn_at_turns,
        )

    # ------------------------------------------------------------------ #
    # Run
    # ------------------------------------------------------------------ #
    def run(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResult:
        """Run the agent with budget enforcement.

        Before dispatching to the underlying runner, the guard checks that
        hard limits have not already been exceeded.  After the run completes,
        it updates running totals and checks warning/limit thresholds.

        Parameters
        ----------
        prompt:
            The user prompt / task.
        context:
            Optional context dictionary.

        Returns
        -------
        AgentResult
            The result from the underlying runner.

        Raises
        ------
        claudekit.errors.BudgetExceededError
            If a hard cost or turn limit would be exceeded.
        """
        # Pre-flight: reject if already over limit
        self._check_pre_limits()

        result = self._runner.run(prompt, context=context)
        self._run_count += 1
        self._total_cost += result.total_cost
        self._total_turns += result.turns

        logger.debug(
            "BudgetGuard: run #%d complete (cost=$%.4f cumulative=$%.4f, "
            "turns=%d cumulative=%d)",
            self._run_count,
            result.total_cost,
            self._total_cost,
            result.turns,
            self._total_turns,
        )

        # Post-run: check warnings and hard limits
        self._check_warnings()
        self._check_post_limits()

        if self._on_complete is not None:
            self._on_complete(result)

        return result

    # ------------------------------------------------------------------ #
    # Interrogation
    # ------------------------------------------------------------------ #
    @property
    def total_cost(self) -> float:
        """Cumulative cost in USD across all runs."""
        return self._total_cost

    @property
    def total_turns(self) -> int:
        """Cumulative turns across all runs."""
        return self._total_turns

    @property
    def run_count(self) -> int:
        """Number of completed runs."""
        return self._run_count

    @property
    def remaining_cost(self) -> Optional[float]:
        """Remaining USD budget, or ``None`` if unlimited."""
        if self._max_cost_usd is None:
            return None
        return max(0.0, self._max_cost_usd - self._total_cost)

    @property
    def remaining_turns(self) -> Optional[int]:
        """Remaining turn allowance, or ``None`` if unlimited."""
        if self._max_turns is None:
            return None
        return max(0, self._max_turns - self._total_turns)

    def reset(self) -> None:
        """Reset running totals and warning flags.

        This does **not** change the configured limits -- only the accumulators.
        """
        self._total_cost = 0.0
        self._total_turns = 0
        self._run_count = 0
        self._cost_warned = False
        self._turns_warned = False
        logger.debug("BudgetGuard: counters reset")

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #
    def _check_pre_limits(self) -> None:
        """Raise before dispatching if already at the ceiling."""
        if self._max_cost_usd is not None and self._total_cost >= self._max_cost_usd:
            self._fire_limit("cost_usd", self._total_cost, self._max_cost_usd)

        if self._max_turns is not None and self._total_turns >= self._max_turns:
            self._fire_limit("turns", float(self._total_turns), float(self._max_turns))

    def _check_post_limits(self) -> None:
        """Raise after a run if we've crossed a hard limit."""
        if self._max_cost_usd is not None and self._total_cost >= self._max_cost_usd:
            self._fire_limit("cost_usd", self._total_cost, self._max_cost_usd)

        if self._max_turns is not None and self._total_turns >= self._max_turns:
            self._fire_limit("turns", float(self._total_turns), float(self._max_turns))

    def _check_warnings(self) -> None:
        """Fire warning callbacks if thresholds are crossed (once only)."""
        if (
            not self._cost_warned
            and self._warn_at_cost_usd is not None
            and self._total_cost >= self._warn_at_cost_usd
        ):
            self._cost_warned = True
            self._on_warn("cost_usd", self._total_cost, self._warn_at_cost_usd)

        if (
            not self._turns_warned
            and self._warn_at_turns is not None
            and self._total_turns >= self._warn_at_turns
        ):
            self._turns_warned = True
            self._on_warn("turns", float(self._total_turns), float(self._warn_at_turns))

    def _fire_limit(self, metric: str, current: float, limit: float) -> None:
        """Fire the on_limit callback and raise :class:`BudgetExceededError`."""
        if self._on_limit is not None:
            self._on_limit(metric, current, limit)

        from claudekit.errors import BudgetExceededError

        raise BudgetExceededError(
            f"Budget limit reached: {metric}={current:.4f} >= {limit:.4f}",
            context={
                "metric": metric,
                "current": current,
                "limit": limit,
                "agent": self._runner.agent.name,
                "run_count": self._run_count,
            },
            recovery_hint=(
                f"Increase the {metric} limit or reduce the workload."
            ),
        )

    @staticmethod
    def _default_warn(metric: str, current: float, threshold: float) -> None:
        """Default warning callback -- logs a warning."""
        logger.warning(
            "BudgetGuard warning: %s=%.4f has reached warning threshold %.4f",
            metric,
            current,
            threshold,
        )

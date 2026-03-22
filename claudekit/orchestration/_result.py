"""OrchestrationResult -- aggregated outcome of an orchestrated run.

Captures the final output, per-agent trace, aggregate cost/token metrics, and
any errors that occurred during parallel execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class OrchestrationResult:
    """Aggregated result from an orchestrated (possibly multi-agent) run.

    Attributes
    ----------
    final_output:
        The textual output produced by the final agent in the chain (or the
        entry agent if no delegation occurred).
    agent_trace:
        Ordered list of trace entries, each a dict with at minimum
        ``{"agent": str, "prompt": str, "output": str, ...}``.
    total_cost:
        Cumulative cost in USD across all agents in this orchestration.
    total_tokens:
        Cumulative token count across all agents.
    duration_seconds:
        Wall-clock time for the entire orchestration.
    errors:
        For parallel runs: maps task index to the exception raised for that
        task.  Empty for single-task runs or fully successful parallel runs.

    Examples
    --------
    >>> result = OrchestrationResult(final_output="Done.", total_cost=0.02)
    >>> result.succeeded
    True
    """

    final_output: str = ""
    agent_trace: list[dict[str, Any]] = field(default_factory=list)
    total_cost: float = 0.0
    total_tokens: int = 0
    duration_seconds: float = 0.0
    errors: dict[int, Exception] = field(default_factory=dict)

    # ------------------------------------------------------------------ #
    # Convenience properties
    # ------------------------------------------------------------------ #
    @property
    def succeeded(self) -> bool:
        """``True`` if the orchestration finished without any errors."""
        return len(self.errors) == 0

    @property
    def failed_task_indices(self) -> list[int]:
        """Indices of tasks that raised an exception (parallel runs only)."""
        return sorted(self.errors.keys())

    @property
    def agents_used(self) -> list[str]:
        """Ordered list of agent names that participated in the orchestration."""
        return [entry["agent"] for entry in self.agent_trace if "agent" in entry]

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"OrchestrationResult(output={self.final_output[:80]!r}..., "
            f"agents={self.agents_used}, total_cost=${self.total_cost:.4f}, "
            f"total_tokens={self.total_tokens}, "
            f"duration={self.duration_seconds:.2f}s, "
            f"errors={len(self.errors)})"
        )

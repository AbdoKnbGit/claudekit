"""Agent dataclass defining an agent's identity and configuration.

An :class:`Agent` captures everything needed to describe *what* an agent is --
its model, system prompt, tools, budget constraints, and platform -- without
coupling to the execution runtime.  Hand an ``Agent`` to
:class:`~claudekit.agents.AgentRunner` or
:class:`~claudekit.orchestration.Orchestrator` to actually execute it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from claudekit._defaults import DEFAULT_MODEL

logger = logging.getLogger(__name__)

_VALID_EFFORTS = frozenset({"low", "medium", "high", "max"})
_VALID_PERMISSION_MODES = frozenset({"default", "acceptEdits", "plan", "bypassPermissions"})
_VALID_PLATFORMS = frozenset({"anthropic", "bedrock", "vertex", "foundry"})


@dataclass
class Agent:
    """Definition of a named agent with its configuration.

    An ``Agent`` is a *declarative* specification.  It does not hold any
    runtime state -- that is the responsibility of the runner or orchestrator.

    Parameters
    ----------
    name:
        Unique identifier for this agent.
    model:
        Model to use, e.g. ``"claude-sonnet-4-6"``.
    system:
        System prompt for the agent.
    tools:
        List of ``@tool``-decorated functions to make available.
    allowed_tools:
        Explicit allow-list of tool names (Agent SDK format).
    disallowed_tools:
        Explicit deny-list of tool names.
    permission_mode:
        One of ``"default"``, ``"acceptEdits"``, ``"plan"``, or ``"bypassPermissions"``.
    max_turns:
        Maximum number of conversational turns before the agent is stopped.
    max_cost_usd:
        Maximum cumulative cost (in USD) for this agent's run.
    effort:
        Reasoning effort: ``"low"`` | ``"medium"`` | ``"high"`` | ``"max"``.
    memory:
        Optional :class:`~claudekit.memory.MemoryStore` for this agent.
    security:
        Optional :class:`~claudekit.security.SecurityLayer` override.
    skills:
        List of :class:`~claudekit.skills.Skill` objects attached to this agent.
    platform:
        Target platform: ``"anthropic"`` | ``"bedrock"`` | ``"vertex"`` | ``"foundry"``.
    timeout_seconds:
        Maximum wall-clock time (seconds) before the run is aborted.
    metadata:
        Arbitrary user metadata dictionary for tagging and filtering.

    Raises
    ------
    claudekit.errors.ConfigurationError
        If any field value is invalid.

    Examples
    --------
    >>> agent = Agent(name="support", model="claude-haiku-4-5", system="You help users.")
    >>> agent.name
    'support'
    """

    name: str
    model: str = DEFAULT_MODEL
    system: str = ""
    tools: list[Any] = field(default_factory=list)
    allowed_tools: Optional[list[str]] = None
    disallowed_tools: Optional[list[str]] = None
    permission_mode: str = "default"
    max_turns: Optional[int] = None
    max_cost_usd: Optional[float] = None
    effort: str = "medium"
    memory: Any = None  # MemoryStore -- lazy to avoid circular import
    security: Any = None  # SecurityLayer
    skills: list[Any] = field(default_factory=list)
    platform: str = "anthropic"
    timeout_seconds: Optional[int] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------ #
    # Validation
    # ------------------------------------------------------------------ #
    def __post_init__(self) -> None:
        """Validate field values on construction."""
        if not self.name:
            from claudekit.errors import ConfigurationError

            raise ConfigurationError(
                "Agent name cannot be empty",
                code="CONFIGURATION_ERROR",
                context={"field": "name"},
                recovery_hint="Provide a non-empty agent name.",
            )

        if self.effort not in _VALID_EFFORTS:
            from claudekit.errors import ConfigurationError

            raise ConfigurationError(
                f"Invalid effort '{self.effort}'",
                code="CONFIGURATION_ERROR",
                context={"field": "effort", "value": self.effort},
                recovery_hint=f"Use one of: {sorted(_VALID_EFFORTS)}",
            )

        if self.permission_mode not in _VALID_PERMISSION_MODES:
            from claudekit.errors import ConfigurationError

            raise ConfigurationError(
                f"Invalid permission_mode '{self.permission_mode}'",
                code="CONFIGURATION_ERROR",
                context={"field": "permission_mode", "value": self.permission_mode},
                recovery_hint=f"Use one of: {sorted(_VALID_PERMISSION_MODES)}",
            )

        if self.platform not in _VALID_PLATFORMS:
            from claudekit.errors import ConfigurationError

            raise ConfigurationError(
                f"Invalid platform '{self.platform}'",
                code="CONFIGURATION_ERROR",
                context={"field": "platform", "value": self.platform},
                recovery_hint=f"Use one of: {sorted(_VALID_PLATFORMS)}",
            )

        if self.max_cost_usd is not None and self.max_cost_usd <= 0:
            from claudekit.errors import ConfigurationError

            raise ConfigurationError(
                f"max_cost_usd must be positive, got {self.max_cost_usd}",
                code="CONFIGURATION_ERROR",
                context={"field": "max_cost_usd", "value": self.max_cost_usd},
                recovery_hint="Set max_cost_usd > 0 or None for unlimited.",
            )

        if self.max_turns is not None and self.max_turns <= 0:
            from claudekit.errors import ConfigurationError

            raise ConfigurationError(
                f"max_turns must be positive, got {self.max_turns}",
                code="CONFIGURATION_ERROR",
                context={"field": "max_turns", "value": self.max_turns},
                recovery_hint="Set max_turns > 0 or None for unlimited.",
            )

        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            from claudekit.errors import ConfigurationError

            raise ConfigurationError(
                f"timeout_seconds must be positive, got {self.timeout_seconds}",
                code="CONFIGURATION_ERROR",
                context={"field": "timeout_seconds", "value": self.timeout_seconds},
                recovery_hint="Set timeout_seconds > 0 or None for unlimited.",
            )

        logger.debug("Agent '%s' created (model=%s, platform=%s)", self.name, self.model, self.platform)

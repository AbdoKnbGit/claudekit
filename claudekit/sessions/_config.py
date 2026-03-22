"""Session configuration dataclass.

Defines :class:`SessionConfig`, the declarative configuration object for
creating managed sessions via :class:`~claudekit.sessions.SessionManager`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

from claudekit.errors import ConfigurationError

logger = logging.getLogger(__name__)


@dataclass
class SessionConfig:
    """Declarative configuration for a managed session.

    Parameters
    ----------
    name:
        Unique human-readable identifier for this session.  Must be non-empty.
    model:
        API model identifier (e.g. ``"claude-sonnet-4-6"``).
    system:
        Optional system prompt.
    memory:
        Optional :class:`~claudekit.memory.MemoryStore` instance to attach.
    security:
        Optional :class:`~claudekit.security.SecurityLayer` instance.
    tools:
        Optional list of tool definitions for tool use.
    max_cost_usd:
        Maximum spend budget in USD.  Must be positive if set.
    max_turns:
        Maximum number of conversation turns.  Must be positive if set.
    timeout_seconds:
        Wall-clock timeout per API call in seconds.
    platform:
        Deployment platform: ``"anthropic"`` (default), ``"bedrock"``,
        or ``"vertex"``.
    shared_context:
        Arbitrary key-value dict available to all callbacks and hooks.
    tags:
        Labels for grouping and filtering sessions.
    on_cost_warning:
        Callback invoked when cost reaches 80% of *max_cost_usd*.
        Signature: ``(session_name: str, current_cost: float, limit: float) -> None``.
    on_error:
        Callback invoked when the session enters the ``"error"`` state.
        Signature: ``(session_name: str, error: Exception) -> None``.
    ignore_broadcasts:
        If ``True``, the session will not receive broadcast events from the
        :class:`SessionManager`.

    Raises
    ------
    ConfigurationError
        If validation fails during ``__post_init__``.

    Example
    -------
    ::

        config = SessionConfig(
            name="summariser",
            model="claude-haiku-4-5",
            max_cost_usd=0.50,
            tags=["batch", "summarise"],
        )
    """

    name: str
    model: str
    system: Optional[str] = None
    memory: Any = None
    security: Any = None
    tools: Optional[list] = None
    max_cost_usd: Optional[float] = None
    max_turns: Optional[int] = None
    timeout_seconds: Optional[int] = None
    max_tokens: Optional[int] = None
    platform: str = "anthropic"
    shared_context: Optional[dict] = field(default=None)
    tags: Optional[List[str]] = field(default=None)
    on_cost_warning: Optional[Callable] = field(default=None, repr=False)
    on_error: Optional[Callable] = field(default=None, repr=False)
    ignore_broadcasts: bool = False

    def __post_init__(self) -> None:
        """Validate configuration values at construction time."""
        if not self.name or not self.name.strip():
            raise ConfigurationError(
                "SessionConfig.name must be a non-empty string.",
                code="CONFIGURATION_ERROR",
                context={"field": "name", "value": self.name},
                recovery_hint="Provide a descriptive session name.",
            )

        if not self.model or not self.model.strip():
            raise ConfigurationError(
                "SessionConfig.model must be a non-empty string.",
                code="CONFIGURATION_ERROR",
                context={"field": "model", "value": self.model},
                recovery_hint="Specify a model identifier such as 'claude-sonnet-4-6'.",
            )

        if self.max_cost_usd is not None and self.max_cost_usd <= 0:
            raise ConfigurationError(
                f"SessionConfig.max_cost_usd must be positive, got {self.max_cost_usd}.",
                code="CONFIGURATION_ERROR",
                context={"field": "max_cost_usd", "value": self.max_cost_usd},
                recovery_hint="Set max_cost_usd to a positive number or None.",
            )

        if self.max_turns is not None and self.max_turns <= 0:
            raise ConfigurationError(
                f"SessionConfig.max_turns must be positive, got {self.max_turns}.",
                code="CONFIGURATION_ERROR",
                context={"field": "max_turns", "value": self.max_turns},
                recovery_hint="Set max_turns to a positive integer or None.",
            )

        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            raise ConfigurationError(
                f"SessionConfig.timeout_seconds must be positive, got {self.timeout_seconds}.",
                code="CONFIGURATION_ERROR",
                context={"field": "timeout_seconds", "value": self.timeout_seconds},
                recovery_hint="Set timeout_seconds to a positive integer or None.",
            )

        if self.platform not in ("anthropic", "bedrock", "vertex"):
            raise ConfigurationError(
                f"SessionConfig.platform must be one of 'anthropic', 'bedrock', "
                f"'vertex', got {self.platform!r}.",
                code="CONFIGURATION_ERROR",
                context={"field": "platform", "value": self.platform},
                recovery_hint="Use 'anthropic', 'bedrock', or 'vertex'.",
            )

        logger.debug(
            "SessionConfig validated: name=%r model=%r platform=%r",
            self.name,
            self.model,
            self.platform,
        )


__all__ = ["SessionConfig"]

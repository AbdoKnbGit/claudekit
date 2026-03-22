"""Fluent batch request builder.

:class:`BatchBuilder` provides a chainable API for constructing lists of
batch request dictionaries compatible with the Anthropic Message Batches
API.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from claudekit._defaults import DEFAULT_FAST_MODEL
from claudekit.errors import ConfigurationError

logger = logging.getLogger(__name__)


class BatchBuilder:
    """Fluent builder for Anthropic batch request payloads.

    Each call to :meth:`add` appends one request to the internal list.
    When all requests have been added, call :meth:`build` to produce the
    final list of batch-request dicts.

    Parameters
    ----------
    default_model:
        Model to use when a request does not specify one.
    default_max_tokens:
        ``max_tokens`` value to use when not overridden per-request.

    Example
    -------
    ::

        builder = (
            BatchBuilder(default_model="claude-haiku-4-5")
            .add("req-1", [{"role": "user", "content": "Hello"}])
            .add("req-2", [{"role": "user", "content": "World"}])
        )
        requests = builder.build()
    """

    def __init__(
        self,
        default_model: str = DEFAULT_FAST_MODEL,
        default_max_tokens: int = 256,
    ) -> None:
        if default_max_tokens <= 0:
            raise ConfigurationError(
                f"default_max_tokens must be positive, got {default_max_tokens}.",
                code="CONFIGURATION_ERROR",
                context={"field": "default_max_tokens", "value": default_max_tokens},
            )
        self._requests: List[Dict[str, Any]] = []
        self.default_model: str = default_model
        self.default_max_tokens: int = default_max_tokens

    def add(
        self,
        custom_id: str,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        system: Optional[str] = None,
        **kwargs: Any,
    ) -> BatchBuilder:
        """Add a request to the batch.

        Args:
            custom_id: Unique identifier for this request within the batch.
                Must be non-empty.
            messages: Message list for this request.
            model: Override the default model for this request.
            max_tokens: Override the default max_tokens for this request.
            system: Optional system prompt for this request.
            **kwargs: Additional parameters forwarded to the API (e.g.,
                ``temperature``, ``thinking``).

        Returns:
            ``self`` for fluent chaining.

        Raises:
            ConfigurationError:
                If *custom_id* is empty or *messages* is empty.
        """
        if not custom_id or not custom_id.strip():
            raise ConfigurationError(
                "custom_id must be a non-empty string.",
                code="CONFIGURATION_ERROR",
                context={"field": "custom_id", "value": custom_id},
            )
        if not messages:
            raise ConfigurationError(
                f"messages must be non-empty for request {custom_id!r}.",
                code="CONFIGURATION_ERROR",
                context={"field": "messages", "custom_id": custom_id},
            )

        params: Dict[str, Any] = {
            "model": model or self.default_model,
            "max_tokens": max_tokens or self.default_max_tokens,
            "messages": messages,
        }
        if system is not None:
            params["system"] = system
        params.update(kwargs)

        request_dict: Dict[str, Any] = {
            "custom_id": custom_id,
            "params": params,
        }

        self._requests.append(request_dict)
        logger.debug("BatchBuilder: added request %r", custom_id)
        return self

    def build(self) -> List[Dict[str, Any]]:
        """Produce the final list of batch request dicts.

        Returns:
            A list of dicts, each containing ``custom_id`` and ``params``.

        Raises:
            ConfigurationError:
                If no requests have been added.
        """
        if not self._requests:
            raise ConfigurationError(
                "Cannot build an empty batch -- add at least one request.",
                code="CONFIGURATION_ERROR",
                recovery_hint="Call .add() before .build().",
            )
        logger.debug("BatchBuilder: built %d requests", len(self._requests))
        return list(self._requests)

    def __len__(self) -> int:
        """Return the number of requests added so far."""
        return len(self._requests)

    def __repr__(self) -> str:
        return (
            f"BatchBuilder(requests={len(self._requests)}, "
            f"default_model={self.default_model!r})"
        )


__all__ = ["BatchBuilder"]

"""Pre-flight token counting to prevent expensive surprises.

Wraps ``client.messages.count_tokens()`` to count tokens BEFORE sending a request,
and provides guard methods to assert the request fits within context limits.

Example:
    >>> from claudekit.precheck import TokenCounter
    >>> counter = TokenCounter(client=client)
    >>> estimate = counter.count(
    ...     model="claude-sonnet-4-6",
    ...     messages=[{"role": "user", "content": very_long_text}],
    ... )
    >>> print(estimate.input_tokens)
    >>> print(estimate.fits_in_context)
    >>> counter.assert_fits("claude-sonnet-4-6", messages, max_percent=0.9)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class TokenCountResult:
    """Result of a pre-flight token count.

    Attributes:
        input_tokens: Number of input tokens counted.
        fits_in_context: Whether the tokens fit in the model's context window.
        estimated_input_cost: Estimated input cost in USD.
        warning: Warning message if near context limit, or None.
        model: The model ID used for counting.
        context_window: The model's context window size.
        percent_used: Percentage of context window used.

    Example:
        >>> result = counter.count(model="claude-haiku-4-5", messages=[...])
        >>> if not result.fits_in_context:
        ...     print(result.warning)
    """

    input_tokens: int
    fits_in_context: bool
    estimated_input_cost: float
    warning: Optional[str]
    model: str
    context_window: int = 0
    percent_used: float = 0.0


class TokenCounter:
    """Pre-flight token counter using the count_tokens API.

    Prevents expensive surprises by counting tokens before sending requests.

    Args:
        client: A TrackedClient or compatible anthropic client.

    Example:
        >>> counter = TokenCounter(client=client)
        >>> estimate = counter.count(
        ...     model="claude-sonnet-4-6",
        ...     messages=[{"role": "user", "content": "Hello"}],
        ... )
        >>> print(estimate.input_tokens)
    """

    def __init__(self, client: Any) -> None:
        self._client = client

    def count(
        self,
        model: str,
        messages: list[dict[str, Any]],
        system: Optional[str] = None,
        tools: Optional[list[Any]] = None,
    ) -> TokenCountResult:
        """Count tokens for a request before sending it.

        Args:
            model: Model ID to count tokens for.
            messages: Messages list.
            system: Optional system prompt.
            tools: Optional tools list.

        Returns:
            TokenCountResult with token count and cost estimate.

        Raises:
            ClaudekitError: If the count_tokens API call fails.

        Example:
            >>> estimate = counter.count("claude-haiku-4-5", [{"role": "user", "content": "Hi"}])
            >>> print(estimate.input_tokens)
        """
        from claudekit.models import get_model

        kwargs: dict[str, Any] = {"model": model, "messages": messages}
        if system is not None:
            kwargs["system"] = system
        if tools is not None:
            tool_defs = []
            for t in tools:
                if hasattr(t, "to_dict"):
                    tool_defs.append(t.to_dict())
                elif isinstance(t, dict):
                    tool_defs.append(t)
                else:
                    tool_defs.append(t)
            kwargs["tools"] = tool_defs

        try:
            # Use the underlying client's count_tokens
            client = getattr(self._client, "_client", self._client)
            result = client.messages.count_tokens(**kwargs)
            input_tokens = result.input_tokens
        except Exception as exc:
            logger.warning("count_tokens API call failed: %s. Falling back to estimate.", exc)
            # Rough estimate: ~4 chars per token
            total_chars = sum(
                len(str(m.get("content", ""))) for m in messages
            )
            if system:
                total_chars += len(system)
            input_tokens = total_chars // 4

        model_info = get_model(model)
        context_window = model_info.context_window if model_info else 200_000
        input_price = model_info.input_per_mtok if model_info else 1.0

        fits = input_tokens <= context_window
        percent_used = (input_tokens / context_window) * 100 if context_window > 0 else 0
        estimated_cost = input_tokens * input_price / 1_000_000

        warning: Optional[str] = None
        if percent_used >= 90:
            warning = f"Near context limit ({percent_used:.1f}% full)"
        elif percent_used >= 75:
            warning = f"Context window {percent_used:.1f}% used"

        if warning:
            logger.info("TokenCounter: %s for model %s", warning, model)

        return TokenCountResult(
            input_tokens=input_tokens,
            fits_in_context=fits,
            estimated_input_cost=estimated_cost,
            warning=warning,
            model=model,
            context_window=context_window,
            percent_used=percent_used,
        )

    def assert_fits(
        self,
        model: str,
        messages: list[dict[str, Any]],
        max_percent: float = 0.9,
        system: Optional[str] = None,
        tools: Optional[list[Any]] = None,
    ) -> None:
        """Assert the request fits within the model's context window.

        Raises ``TokenLimitError`` if the request exceeds ``max_percent``
        of the model's context window.

        Args:
            model: Model ID.
            messages: Messages list.
            max_percent: Maximum allowed context usage (0.0-1.0). Default 0.9 (90%).
            system: Optional system prompt.
            tools: Optional tools list.

        Raises:
            TokenLimitError: If request exceeds the allowed context percentage.

        Example:
            >>> counter.assert_fits("claude-sonnet-4-6", messages, max_percent=0.9)
        """
        result = self.count(model, messages, system=system, tools=tools)
        threshold = result.context_window * max_percent

        if result.input_tokens > threshold:
            from claudekit.errors import TokenLimitError

            raise TokenLimitError(
                f"Request uses {result.input_tokens:,} tokens "
                f"({result.percent_used:.1f}% of {result.context_window:,} context window), "
                f"exceeding {max_percent:.0%} limit",
                code="TOKEN_LIMIT_EXCEEDED",
                context={
                    "model": model,
                    "input_tokens": result.input_tokens,
                    "context_window": result.context_window,
                    "percent_used": result.percent_used,
                    "max_percent": max_percent * 100,
                },
                recovery_hint=(
                    "Reduce message content, split into smaller requests, "
                    "or use a model with a larger context window."
                ),
            )

        logger.debug(
            "assert_fits passed: %d tokens (%.1f%% of %d)",
            result.input_tokens,
            result.percent_used,
            result.context_window,
        )

"""Helpers for configuring extended and adaptive thinking.

Extended thinking allows Claude to reason through complex problems before
responding. Adaptive thinking lets the model decide when thinking is beneficial.

Example:
    >>> from claudekit.thinking import thinking_enabled, extract_thinking
    >>> response = client.messages.create(
    ...     model="claude-opus-4-6",
    ...     max_tokens=16000,
    ...     thinking=thinking_enabled(budget_tokens=10000),
    ...     messages=[{"role": "user", "content": "Solve this complex problem..."}],
    ... )
    >>> thoughts, answer = extract_thinking(response)
"""

from __future__ import annotations

from typing import Any


def thinking_enabled(budget_tokens: int) -> dict[str, Any]:
    """Return thinking config with type='enabled'.

    Use this when you always want the model to think before responding.

    Args:
        budget_tokens: Maximum tokens the model can use for thinking.

    Returns:
        Dict suitable for the ``thinking`` parameter of ``messages.create()``.

    Example:
        >>> thinking_enabled(10000)
        {'type': 'enabled', 'budget_tokens': 10000}
    """
    if budget_tokens <= 0:
        from claudekit.errors import ConfigurationError
        raise ConfigurationError(
            f"budget_tokens must be positive, got {budget_tokens}",
            code="CONFIGURATION_ERROR",
            context={"field": "budget_tokens", "value": budget_tokens},
            recovery_hint="Set budget_tokens > 0.",
        )
    return {"type": "enabled", "budget_tokens": budget_tokens}


def thinking_adaptive(budget_tokens: int) -> dict[str, Any]:
    """Return thinking config with type='adaptive' (recommended for most use cases).

    Adaptive thinking lets the model decide when thinking is beneficial.

    Args:
        budget_tokens: Maximum tokens the model can use for thinking.

    Returns:
        Dict suitable for the ``thinking`` parameter of ``messages.create()``.

    Example:
        >>> thinking_adaptive(5000)
        {'type': 'adaptive', 'budget_tokens': 5000}
    """
    if budget_tokens <= 0:
        from claudekit.errors import ConfigurationError
        raise ConfigurationError(
            f"budget_tokens must be positive, got {budget_tokens}",
            code="CONFIGURATION_ERROR",
            context={"field": "budget_tokens", "value": budget_tokens},
            recovery_hint="Set budget_tokens > 0.",
        )
    return {"type": "adaptive", "budget_tokens": budget_tokens}


def thinking_disabled() -> dict[str, str]:
    """Return thinking config with type='disabled'.

    Returns:
        Dict suitable for the ``thinking`` parameter of ``messages.create()``.

    Example:
        >>> thinking_disabled()
        {'type': 'disabled'}
    """
    return {"type": "disabled"}


def extract_thinking(response: Any) -> tuple[str, str]:
    """Extract thinking blocks and final text answer from a response.

    Separates the model's internal reasoning (thinking blocks) from the
    final text answer (text blocks).

    Args:
        response: An ``anthropic.types.Message`` or compatible object with
            a ``.content`` list of blocks.

    Returns:
        A tuple of ``(thinking_text, answer_text)``. Either may be empty
        if no blocks of that type are present.

    Example:
        >>> thoughts, answer = extract_thinking(response)
        >>> print(thoughts)  # the reasoning
        >>> print(answer)    # the final answer
    """
    thinking_parts: list[str] = []
    text_parts: list[str] = []

    for block in getattr(response, "content", []):
        block_type = getattr(block, "type", "")
        if block_type == "thinking":
            thinking_text = getattr(block, "thinking", "")
            if thinking_text:
                thinking_parts.append(thinking_text)
        elif block_type == "text":
            text = getattr(block, "text", "")
            if text:
                text_parts.append(text)

    return "\n".join(thinking_parts), "\n".join(text_parts)

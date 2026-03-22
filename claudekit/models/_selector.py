"""Constraint-based model selection.

Provides :func:`select_model` which picks the best Claude model for a given
set of requirements (task complexity, budget, feature needs, platform).
"""

from __future__ import annotations

import enum
import logging
import warnings
from typing import Optional

from ._registry import MODELS, Model, get_model

logger = logging.getLogger(__name__)


class ModelTask(enum.Enum):
    """Task complexity levels for automatic model selection.

    Members:
        SIMPLE: Low-complexity tasks (classification, extraction, short Q&A).
            Maps to Haiku.
        BALANCED: Medium-complexity tasks (summarisation, code generation,
            multi-step reasoning). Maps to Sonnet.
        COMPLEX: High-complexity tasks (research, long-form writing,
            advanced analysis). Maps to Opus.
    """

    SIMPLE = "simple"
    BALANCED = "balanced"
    COMPLEX = "complex"


def _id_matches(model: Model, target_id: str) -> bool:
    """Check if *target_id* matches the model's api_id or any of its aliases."""
    return model.api_id == target_id or target_id in model.aliases


_TASK_MAP: dict[ModelTask, str] = {
    ModelTask.SIMPLE: "claude-haiku-4-5",
    ModelTask.BALANCED: "claude-sonnet-4-6",
    ModelTask.COMPLEX: "claude-opus-4-6",
}


def _platform_id(model: Model, platform: str) -> str:
    """Return the model identifier for the requested platform.

    Args:
        model: The resolved :class:`Model`.
        platform: One of ``"anthropic"``, ``"bedrock"``, ``"vertex"``,
            or ``"foundry"``.

    Returns:
        The platform-specific model identifier string.

    Raises:
        ValueError: If the platform is unknown or the model has no ID for it.
    """
    if platform == "anthropic":
        return model.api_id
    if platform == "bedrock":
        if model.bedrock_id is None:
            raise ValueError(
                f"Model {model.api_id!r} is not available on AWS Bedrock."
            )
        return model.bedrock_id
    if platform == "vertex":
        if model.vertex_id is None:
            raise ValueError(
                f"Model {model.api_id!r} is not available on Google Vertex AI."
            )
        return model.vertex_id
    if platform == "foundry":
        # Microsoft Foundry uses the same API model identifiers.
        return model.api_id
    raise ValueError(
        f"Unknown platform {platform!r}. "
        "Supported platforms: 'anthropic', 'bedrock', 'vertex', 'foundry'."
    )


def _resolve_deprecation(model: Model) -> Model:
    """If *model* is deprecated, follow the replacement chain.

    Emits a :class:`DeprecationWarning` and logs at WARNING level for every
    deprecated hop.

    Returns:
        A non-deprecated :class:`Model`, or the original model if no
        replacement is available.
    """
    visited: set[str] = set()
    current = model
    while current.is_deprecated:
        msg = (
            f"Model {current.api_id!r} is deprecated"
            + (f" (EOL {current.eol_date})" if current.eol_date else "")
            + "."
        )
        if current.recommended_replacement:
            replacement = get_model(current.recommended_replacement)
            if replacement is not None and replacement.api_id not in visited:
                msg += f" Using replacement {replacement.api_id!r}."
                warnings.warn(msg, DeprecationWarning, stacklevel=3)
                logger.warning(msg)
                visited.add(current.api_id)
                current = replacement
                continue
        # No valid replacement found; warn and return as-is.
        msg += " No replacement available; returning deprecated model."
        warnings.warn(msg, DeprecationWarning, stacklevel=3)
        logger.warning(msg)
        break
    return current


def select_model(
    task: Optional[ModelTask] = None,
    max_cost_usd: Optional[float] = None,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    require_thinking: bool = False,
    require_vision: bool = False,
    prefer_speed: bool = False,
    platform: str = "anthropic",
) -> str:
    """Pick the best Claude model given a set of constraints.

    Selection logic (in order of priority):

    1. If *task* is provided, start with its mapped model.
    2. Filter candidates by hard requirements (*require_thinking*,
       *require_vision*).
    3. If *max_cost_usd* is set together with token estimates, exclude models
       whose estimated cost exceeds the budget.
    4. If *prefer_speed* is ``True``, prefer cheaper / faster models among
       remaining candidates.
    5. If the chosen model is deprecated, transparently swap in its
       recommended replacement and emit a :class:`DeprecationWarning`.

    Args:
        task: Desired complexity tier.  When ``None``, defaults to
            :attr:`ModelTask.BALANCED`.
        max_cost_usd: Maximum acceptable cost in USD for the call.  Only
            effective when *input_tokens* and *output_tokens* are also given.
        input_tokens: Estimated number of input tokens for cost filtering.
        output_tokens: Estimated number of output tokens for cost filtering.
        require_thinking: If ``True``, only consider models that support
            extended thinking.
        require_vision: If ``True``, only consider models that support image
            input.
        prefer_speed: If ``True``, prefer the cheapest eligible model (i.e.
            the one with the lowest input price per million tokens).
        platform: Target deployment platform.  One of ``"anthropic"``
            (default), ``"bedrock"``, ``"vertex"``, or ``"foundry"``.

    Returns:
        The platform-specific model identifier string.

    Raises:
        ValueError: If no model satisfies all constraints or the platform
            is unknown.

    Examples::

        >>> select_model(task=ModelTask.SIMPLE)
        'claude-haiku-4-5'

        >>> select_model(task=ModelTask.COMPLEX, platform="bedrock")
        'anthropic.claude-opus-4-6-v1'

        >>> select_model(
        ...     max_cost_usd=0.01,
        ...     input_tokens=10_000,
        ...     output_tokens=2_000,
        ... )
        'claude-haiku-4-5'

        >>> select_model(require_thinking=True, prefer_speed=True)
        'claude-haiku-4-5'
    """
    # ------------------------------------------------------------------
    # 1. Build candidate pool
    # ------------------------------------------------------------------
    candidates: list[Model] = list(MODELS)

    # ------------------------------------------------------------------
    # 2. Hard-requirement filters
    # ------------------------------------------------------------------
    if require_thinking:
        candidates = [m for m in candidates if m.supports_thinking]
    if require_vision:
        candidates = [m for m in candidates if m.supports_vision]

    # Filter by platform availability
    if platform == "bedrock":
        candidates = [m for m in candidates if m.bedrock_id is not None]
    elif platform == "vertex":
        candidates = [m for m in candidates if m.vertex_id is not None]

    if not candidates:
        raise ValueError(
            "No model satisfies the given constraints "
            f"(require_thinking={require_thinking}, "
            f"require_vision={require_vision}, platform={platform!r})."
        )

    # ------------------------------------------------------------------
    # 3. Budget filter (only when token estimates are provided)
    # ------------------------------------------------------------------
    if max_cost_usd is not None and input_tokens is not None and output_tokens is not None:
        affordable = [
            m
            for m in candidates
            if m.estimate_cost(input_tokens, output_tokens) <= max_cost_usd
        ]
        if affordable:
            candidates = affordable
        else:
            # None are affordable; warn and keep all so we can still return
            # the cheapest option below.
            logger.warning(
                "No model fits within the budget of $%.4f for %d input / "
                "%d output tokens. Selecting the cheapest available model.",
                max_cost_usd,
                input_tokens,
                output_tokens,
            )

    # ------------------------------------------------------------------
    # 4. Task-based or speed-based selection
    # ------------------------------------------------------------------
    if prefer_speed:
        # Sort by input cost ascending (cheapest = fastest tier).
        candidates.sort(key=lambda m: m.input_per_mtok)
        chosen = candidates[0]
    elif task is not None:
        # Try the mapped model first; fall back to cheapest candidate.
        target_id = _TASK_MAP[task]
        matched = [m for m in candidates if _id_matches(m, target_id)]
        if matched:
            chosen = matched[0]
        else:
            # The ideal model was filtered out; pick the best remaining.
            # Sort descending by cost so the most capable survivor wins.
            candidates.sort(key=lambda m: m.input_per_mtok, reverse=True)
            chosen = candidates[0]
    else:
        # Default to BALANCED behaviour.
        target_id = _TASK_MAP[ModelTask.BALANCED]
        matched = [m for m in candidates if _id_matches(m, target_id)]
        if matched:
            chosen = matched[0]
        else:
            candidates.sort(key=lambda m: m.input_per_mtok, reverse=True)
            chosen = candidates[0]

    # ------------------------------------------------------------------
    # 5. Deprecation handling
    # ------------------------------------------------------------------
    chosen = _resolve_deprecation(chosen)

    # ------------------------------------------------------------------
    # 6. Return platform-specific identifier
    # ------------------------------------------------------------------
    return _platform_id(chosen, platform)

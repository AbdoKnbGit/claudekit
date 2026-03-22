"""Model registry with accurate pricing and capabilities.

Pricing data sourced from https://docs.anthropic.com/en/docs/about-claude/pricing
Model IDs sourced from https://docs.anthropic.com/en/docs/about-claude/models/overview
Deprecation data from https://docs.anthropic.com/en/docs/about-claude/model-deprecations
Last verified: 2026-03-20
NOTE: Pricing WILL change. Verify against the official pricing page periodically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Model:
    """Represents a Claude model with pricing and capabilities.

    Attributes:
        name: Human-readable display name.
        api_id: Exact API model string (with date snapshot where applicable).
        aliases: Alternative API IDs that resolve to this model (e.g. short names).
        bedrock_id: AWS Bedrock model identifier, if available.
        vertex_id: Google Vertex AI model identifier, if available.
        input_per_mtok: Cost per million input tokens in USD.
        output_per_mtok: Cost per million output tokens in USD.
        cache_read_per_mtok: Cost per million cache-read tokens (0.1x input).
        cache_write_per_mtok: Cost per million cache-write tokens (1.25x input).
        context_window: Maximum context window size in tokens.
        max_output_tokens: Maximum output tokens.
        supports_thinking: Whether extended thinking is supported.
        supports_vision: Whether image input is supported.
        supports_streaming: Whether streaming is supported.
        is_deprecated: Whether the model is deprecated or retired.
        eol_date: End-of-life / retirement date string (ISO-8601).
        recommended_replacement: Suggested replacement model ``api_id``.

    Example::

        >>> model = MODELS_BY_ID["claude-sonnet-4-6"]
        >>> model.estimate_cost(1000, 500)
        0.0105
    """

    name: str
    api_id: str
    aliases: tuple[str, ...] = ()
    bedrock_id: Optional[str] = None
    vertex_id: Optional[str] = None
    input_per_mtok: float = 0.0
    output_per_mtok: float = 0.0
    cache_read_per_mtok: float = 0.0
    cache_write_per_mtok: float = 0.0
    context_window: int = 200_000
    max_output_tokens: int = 8192
    supports_thinking: bool = False
    supports_vision: bool = True
    supports_streaming: bool = True
    is_deprecated: bool = False
    eol_date: Optional[str] = None
    recommended_replacement: Optional[str] = None

    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
    ) -> float:
        """Estimate cost in USD for given token counts.

        Args:
            input_tokens: Number of input tokens (non-cached).
            output_tokens: Number of output tokens.
            cache_read_tokens: Number of cache-read tokens.
            cache_write_tokens: Number of cache-write tokens.

        Returns:
            Estimated cost in USD.

        Example::

            >>> model = MODELS_BY_ID["claude-sonnet-4-6"]
            >>> model.estimate_cost(1_000_000, 0)
            3.0
        """
        cost = (
            input_tokens * self.input_per_mtok / 1_000_000
            + output_tokens * self.output_per_mtok / 1_000_000
            + cache_read_tokens * self.cache_read_per_mtok / 1_000_000
            + cache_write_tokens * self.cache_write_per_mtok / 1_000_000
        )
        return cost

    def fits_in_context(self, token_count: int) -> bool:
        """Check if the given token count fits in this model's context window.

        Args:
            token_count: Number of tokens to check.

        Returns:
            True if tokens fit within the context window.
        """
        return token_count <= self.context_window


# ---------------------------------------------------------------------------
# All models as of 2026-03-20
# Source: https://docs.anthropic.com/en/docs/about-claude/pricing
#         https://docs.anthropic.com/en/docs/about-claude/models/overview
#         https://docs.anthropic.com/en/docs/about-claude/model-deprecations
# ---------------------------------------------------------------------------
MODELS: list[Model] = [
    # ===================================================================== #
    # LATEST (Active)
    # ===================================================================== #
    Model(
        name="Claude Opus 4.6",
        api_id="claude-opus-4-6",
        # Opus 4.6 has no date-snapshot suffix; the ID *is* the alias.
        aliases=(),
        bedrock_id="anthropic.claude-opus-4-6-v1",
        vertex_id="claude-opus-4-6",
        input_per_mtok=5.0,
        output_per_mtok=25.0,
        cache_read_per_mtok=0.50,          # 0.1x input
        cache_write_per_mtok=6.25,         # 1.25x input
        context_window=1_000_000,
        max_output_tokens=128_000,
        supports_thinking=True,
        supports_vision=True,
    ),
    Model(
        name="Claude Sonnet 4.6",
        api_id="claude-sonnet-4-6",
        aliases=(),
        bedrock_id="anthropic.claude-sonnet-4-6",
        vertex_id="claude-sonnet-4-6",
        input_per_mtok=3.0,
        output_per_mtok=15.0,
        cache_read_per_mtok=0.30,          # 0.1x input
        cache_write_per_mtok=3.75,         # 1.25x input
        context_window=1_000_000,
        max_output_tokens=64_000,
        supports_thinking=True,
        supports_vision=True,
    ),
    Model(
        name="Claude Haiku 4.5",
        api_id="claude-haiku-4-5-20251001",
        aliases=("claude-haiku-4-5",),
        bedrock_id="anthropic.claude-haiku-4-5-20251001-v1:0",
        vertex_id="claude-haiku-4-5@20251001",
        input_per_mtok=1.0,
        output_per_mtok=5.0,
        cache_read_per_mtok=0.10,          # 0.1x input
        cache_write_per_mtok=1.25,         # 1.25x input
        context_window=200_000,
        max_output_tokens=64_000,
        supports_thinking=True,
        supports_vision=True,
    ),
    # ===================================================================== #
    # LEGACY (Active, but superseded by latest)
    # ===================================================================== #
    Model(
        name="Claude Opus 4.5",
        api_id="claude-opus-4-5-20251101",
        aliases=("claude-opus-4-5",),
        bedrock_id="anthropic.claude-opus-4-5-20251101-v1:0",
        vertex_id="claude-opus-4-5@20251101",
        input_per_mtok=5.0,
        output_per_mtok=25.0,
        cache_read_per_mtok=0.50,
        cache_write_per_mtok=6.25,

        context_window=200_000,
        max_output_tokens=64_000,
        supports_thinking=True,
        supports_vision=True,
    ),
    Model(
        name="Claude Sonnet 4.5",
        api_id="claude-sonnet-4-5-20250929",
        aliases=("claude-sonnet-4-5",),
        bedrock_id="anthropic.claude-sonnet-4-5-20250929-v1:0",
        vertex_id="claude-sonnet-4-5@20250929",
        input_per_mtok=3.0,
        output_per_mtok=15.0,
        cache_read_per_mtok=0.30,
        cache_write_per_mtok=3.75,

        context_window=200_000,            # 1M available via beta header
        max_output_tokens=64_000,
        supports_thinking=True,
        supports_vision=True,
    ),
    Model(
        name="Claude Opus 4.1",
        api_id="claude-opus-4-1-20250805",
        aliases=("claude-opus-4-1",),
        bedrock_id="anthropic.claude-opus-4-1-20250805-v1:0",
        vertex_id="claude-opus-4-1@20250805",
        input_per_mtok=15.0,
        output_per_mtok=75.0,
        cache_read_per_mtok=1.50,
        cache_write_per_mtok=18.75,

        context_window=200_000,
        max_output_tokens=32_000,
        supports_thinking=True,
        supports_vision=True,
    ),
    Model(
        name="Claude Sonnet 4",
        api_id="claude-sonnet-4-20250514",
        aliases=("claude-sonnet-4-0",),
        bedrock_id="anthropic.claude-sonnet-4-20250514-v1:0",
        vertex_id="claude-sonnet-4@20250514",
        input_per_mtok=3.0,
        output_per_mtok=15.0,
        cache_read_per_mtok=0.30,
        cache_write_per_mtok=3.75,

        context_window=200_000,            # 1M available via beta header
        max_output_tokens=64_000,
        supports_thinking=True,
        supports_vision=True,
    ),
    Model(
        name="Claude Opus 4",
        api_id="claude-opus-4-20250514",
        aliases=("claude-opus-4-0",),
        bedrock_id="anthropic.claude-opus-4-20250514-v1:0",
        vertex_id="claude-opus-4@20250514",
        input_per_mtok=15.0,
        output_per_mtok=75.0,
        cache_read_per_mtok=1.50,
        cache_write_per_mtok=18.75,

        context_window=200_000,
        max_output_tokens=32_000,
        supports_thinking=True,
        supports_vision=True,
    ),
    Model(
        name="Claude Haiku 3.5",
        api_id="claude-3-5-haiku-20241022",
        aliases=("claude-haiku-3-5",),
        bedrock_id="anthropic.claude-3-5-haiku-20241022-v1:0",
        vertex_id="claude-3-5-haiku@20241022",
        input_per_mtok=0.80,
        output_per_mtok=4.0,
        cache_read_per_mtok=0.08,
        cache_write_per_mtok=1.0,

        context_window=200_000,
        max_output_tokens=8_192,
        supports_thinking=False,
        supports_vision=True,
        is_deprecated=True,
        eol_date="2026-02-19",
        recommended_replacement="claude-haiku-4-5-20251001",
    ),
    # ===================================================================== #
    # DEPRECATED / RETIRED
    # ===================================================================== #
    Model(
        name="Claude Sonnet 3.7",
        api_id="claude-3-7-sonnet-20250219",
        aliases=(),
        bedrock_id="anthropic.claude-3-7-sonnet-20250219-v1:0",
        vertex_id="claude-3-7-sonnet@20250219",
        input_per_mtok=3.0,
        output_per_mtok=15.0,
        cache_read_per_mtok=0.30,
        cache_write_per_mtok=3.75,

        context_window=200_000,
        max_output_tokens=64_000,
        supports_thinking=True,
        supports_vision=True,
        is_deprecated=True,
        eol_date="2026-02-19",
        recommended_replacement="claude-sonnet-4-6",
    ),
    Model(
        name="Claude Haiku 3",
        api_id="claude-3-haiku-20240307",
        aliases=(),
        bedrock_id="anthropic.claude-3-haiku-20240307-v1:0",
        vertex_id="claude-3-haiku@20240307",
        input_per_mtok=0.25,
        output_per_mtok=1.25,
        cache_read_per_mtok=0.03,
        cache_write_per_mtok=0.30,

        context_window=200_000,
        max_output_tokens=4_096,
        supports_thinking=False,
        supports_vision=True,
        is_deprecated=True,
        eol_date="2026-04-20",
        recommended_replacement="claude-haiku-4-5-20251001",
    ),
    Model(
        name="Claude Opus 3",
        api_id="claude-3-opus-20240229",
        aliases=(),
        bedrock_id="anthropic.claude-3-opus-20240229-v1:0",
        vertex_id="claude-3-opus@20240229",
        input_per_mtok=15.0,
        output_per_mtok=75.0,
        cache_read_per_mtok=1.50,
        cache_write_per_mtok=18.75,

        context_window=200_000,
        max_output_tokens=4_096,
        supports_thinking=False,
        supports_vision=True,
        is_deprecated=True,
        eol_date="2026-01-05",
        recommended_replacement="claude-opus-4-6",
    ),
]


def _build_lookup() -> dict[str, Model]:
    """Build a lookup dict mapping every api_id AND alias to its Model."""
    lookup: dict[str, Model] = {}
    for m in MODELS:
        lookup[m.api_id] = m
        for alias in m.aliases:
            lookup[alias] = m
    return lookup


MODELS_BY_ID: dict[str, Model] = _build_lookup()
MODELS_BY_NAME: dict[str, Model] = {m.name: m for m in MODELS}


def get_model(model_id: str) -> Optional[Model]:
    """Look up a model by its API ID or alias.

    Both full snapshot IDs (e.g. ``"claude-haiku-4-5-20251001"``) and short
    aliases (e.g. ``"claude-haiku-4-5"``) are supported.

    Args:
        model_id: The API model identifier string.

    Returns:
        The :class:`Model` if found, ``None`` otherwise.

    Example::

        >>> get_model("claude-haiku-4-5-20251001")
        Model(name='Claude Haiku 4.5', ...)
        >>> get_model("claude-haiku-4-5")  # alias works too
        Model(name='Claude Haiku 4.5', ...)
    """
    return MODELS_BY_ID.get(model_id)

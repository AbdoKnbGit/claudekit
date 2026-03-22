"""Unified client factory with automatic platform detection.

Provides :func:`create_client`, which inspects environment variables (or an
explicit ``platform`` argument) to instantiate the correct tracked client
for the caller's deployment target.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional, Union

from claudekit.client._session import SessionUsage

logger = logging.getLogger(__name__)


def create_client(
    platform: Optional[str] = None,
    api_key: Optional[str] = None,
    security: Any = None,
    memory: Any = None,
    plugins: Any = None,
    **kwargs: Any,
) -> Any:
    """Create a tracked client, auto-detecting platform from environment.

    Platform detection order (when *platform* is ``None``):

    1. ``CLAUDE_CODE_USE_BEDROCK=1`` in environment -> :class:`TrackedBedrockClient`
    2. ``CLAUDE_CODE_USE_VERTEX=1`` in environment -> :class:`TrackedVertexClient`
    3. ``CLAUDE_CODE_USE_FOUNDRY=1`` in environment -> :class:`TrackedFoundryClient`
    4. Otherwise -> :class:`TrackedClient` (direct Anthropic API)

    Or pass *platform* explicitly as one of ``"anthropic"``, ``"bedrock"``,
    ``"vertex"``, ``"foundry"``.

    Args:
        platform: Explicit platform selection.  One of ``"anthropic"``,
            ``"bedrock"``, ``"vertex"``, ``"foundry"``, or ``None`` for
            auto-detection.
        api_key: Anthropic API key (only used for direct API platform).
            Falls back to the ``ANTHROPIC_API_KEY`` environment variable.
        security: Optional security layer instance to attach to the client.
        memory: Optional memory store instance to attach to the client.
        plugins: Reserved for future plugin support.  Currently unused.
        **kwargs: Additional keyword arguments forwarded to the underlying
            client constructor (e.g., ``aws_region`` for Bedrock,
            ``project_id`` for Vertex).

    Returns:
        A tracked client instance.  The concrete type depends on the
        selected platform:

        - ``"anthropic"`` -> :class:`~claudekit.client.TrackedClient`
        - ``"bedrock"`` -> :class:`~claudekit.client.TrackedBedrockClient`
        - ``"vertex"`` -> :class:`~claudekit.client.TrackedVertexClient`
        - ``"foundry"`` -> :class:`~claudekit.client.TrackedFoundryClient`

    Raises:
        ValueError: If *platform* is not a recognised value.
        claudekit.errors.PlatformNotAvailableError: If the required SDK
            extra for the detected platform is not installed.

    Example::

        from claudekit.client import create_client

        # Auto-detect from environment
        client = create_client()

        # Explicit platform
        client = create_client(platform="bedrock", aws_region="us-east-1")
    """
    resolved = _resolve_platform(platform)
    logger.debug("Creating tracked client for platform=%r", resolved)

    if resolved == "bedrock":
        from claudekit.client._bedrock import TrackedBedrockClient

        return TrackedBedrockClient(security=security, memory=memory, **kwargs)

    if resolved == "vertex":
        from claudekit.client._vertex import TrackedVertexClient

        return TrackedVertexClient(security=security, memory=memory, **kwargs)

    if resolved == "foundry":
        from claudekit.client._foundry import TrackedFoundryClient

        return TrackedFoundryClient(security=security, memory=memory, **kwargs)

    # Default: direct Anthropic API
    from claudekit.client._tracked import TrackedClient

    return TrackedClient(api_key=api_key, security=security, memory=memory, **kwargs)


def _resolve_platform(platform: Optional[str]) -> str:
    """Resolve the platform string, falling back to env-var detection.

    Args:
        platform: Explicit platform name, or ``None`` to auto-detect.

    Returns:
        One of ``"anthropic"``, ``"bedrock"``, ``"vertex"``, ``"foundry"``.

    Raises:
        ValueError: If *platform* is not a recognised value.
    """
    valid_platforms = {"anthropic", "bedrock", "vertex", "foundry"}

    if platform is not None:
        normalised = platform.strip().lower()
        if normalised not in valid_platforms:
            raise ValueError(
                f"Unknown platform {platform!r}. "
                f"Supported platforms: {', '.join(sorted(valid_platforms))}"
            )
        return normalised

    # Auto-detect from environment variables
    if os.environ.get("CLAUDE_CODE_USE_BEDROCK", "").strip() == "1":
        logger.info("Auto-detected platform: bedrock (CLAUDE_CODE_USE_BEDROCK=1)")
        return "bedrock"

    if os.environ.get("CLAUDE_CODE_USE_VERTEX", "").strip() == "1":
        logger.info("Auto-detected platform: vertex (CLAUDE_CODE_USE_VERTEX=1)")
        return "vertex"

    if os.environ.get("CLAUDE_CODE_USE_FOUNDRY", "").strip() == "1":
        logger.info("Auto-detected platform: foundry (CLAUDE_CODE_USE_FOUNDRY=1)")
        return "foundry"

    return "anthropic"

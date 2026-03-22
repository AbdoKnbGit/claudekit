"""Central default model constants.

All default model references across claudekit import from here so there
is exactly **one** place to change when upgrading the default model tier.

If the user does not explicitly choose a model, these are used:

- ``DEFAULT_MODEL``: General-purpose default (Sonnet — balanced cost/quality).
- ``DEFAULT_FAST_MODEL``: For lightweight / routing / classification tasks (Haiku).
- ``DEFAULT_POWERFUL_MODEL``: For complex reasoning / research tasks (Opus).
"""

from __future__ import annotations

# ── General-purpose default ─────────────────────────────────────────────── #
DEFAULT_MODEL: str = "claude-sonnet-4-6"
"""Used when no model is specified for general-purpose tasks."""

# ── Lightweight / fast tasks ────────────────────────────────────────────── #
DEFAULT_FAST_MODEL: str = "claude-haiku-4-5-20251001"
"""Used for routing, classification, summarisation, and other lightweight tasks."""

# ── Complex / powerful tasks ────────────────────────────────────────────── #
DEFAULT_POWERFUL_MODEL: str = "claude-opus-4-6"
"""Used for research, deep analysis, and code review."""

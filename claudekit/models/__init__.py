"""Model registry, pricing data, and constraint-based selection.

This module exposes the canonical list of supported Claude models together with
their pricing and capability metadata, plus a convenience function for picking
the right model given runtime constraints.

Quick start::

    from claudekit.models import get_model, select_model, ModelTask

    # Look up a specific model
    haiku = get_model("claude-haiku-4-5")
    print(haiku.estimate_cost(input_tokens=10_000, output_tokens=2_000))

    # Let the library choose
    model_id = select_model(task=ModelTask.BALANCED, platform="bedrock")
"""

from __future__ import annotations

from ._registry import MODELS, MODELS_BY_ID, MODELS_BY_NAME, Model, get_model
from ._selector import ModelTask, select_model

__all__ = [
    "Model",
    "MODELS",
    "MODELS_BY_ID",
    "MODELS_BY_NAME",
    "ModelTask",
    "get_model",
    "select_model",
]

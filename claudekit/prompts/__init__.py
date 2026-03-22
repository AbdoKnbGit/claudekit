"""claudekit.prompts -- Versioned prompt storage, diff, and A/B comparison.

Quick start::

    from claudekit.prompts import PromptManager

    pm = PromptManager()
    pm.save("support", system="Be concise.", version="1.0")
    pm.save("support", system="Be concise and empathetic.", version="2.0")
    print(pm.diff("support", "1.0", "2.0"))
"""

from __future__ import annotations

from claudekit.prompts._comparison import ComparisonResult
from claudekit.prompts._manager import PromptManager
from claudekit.prompts._storage import JSONPromptStorage
from claudekit.prompts._version import PromptVersion

__all__ = [
    "ComparisonResult",
    "JSONPromptStorage",
    "PromptManager",
    "PromptVersion",
]

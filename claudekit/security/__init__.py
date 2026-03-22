"""claudekit.security -- Composable security policy framework.

Provides :class:`SecurityLayer` as the main entry point, :class:`Policy` as the
base class for custom policies, and :class:`SecurityContext` carrying per-request
metadata.

Quick start::

    from claudekit.security import SecurityLayer, Policy

    layer = SecurityLayer([
        Policy.no_prompt_injection(),
        Policy.no_pii_in_output(action="redact"),
        Policy.rate_limit(requests_per_minute=30),
    ])
"""

from __future__ import annotations

from claudekit.security._context import SecurityContext
from claudekit.security._layer import SecurityLayer
from claudekit.security._policy import Policy

__all__ = [
    "Policy",
    "SecurityContext",
    "SecurityLayer",
]

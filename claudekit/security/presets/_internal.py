"""Internal tools security preset.

For: internal developer tools, back-office automation.
Includes: PromptInjectionPolicy(low), PIIPolicy(warn, api_key only),
RateLimitPolicy(1000/hour).
Excludes: JailbreakPolicy (internal users are trusted).
"""

from __future__ import annotations

from typing import Any, List, Optional

from claudekit.security._layer import SecurityLayer


class InternalToolsPreset(SecurityLayer):
    """Pre-configured security for internal tools and back-office automation.

    Lighter security posture appropriate for trusted internal users.

    Parameters
    ----------
    override_policies:
        Additional policies to append.
    exclude_policies:
        Names of built-in policies to remove.

    Example
    -------
    ::

        from claudekit.security.presets import InternalToolsPreset

        security = InternalToolsPreset()
    """

    def __init__(
        self,
        override_policies: Optional[List[Any]] = None,
        exclude_policies: Optional[List[str]] = None,
    ) -> None:
        from claudekit.security.policies._injection import PromptInjectionPolicy
        from claudekit.security.policies._pii import PIIPolicy
        from claudekit.security.policies._rate_limit import RateLimitPolicy

        policies: list[Any] = [
            RateLimitPolicy(requests_per_hour=1000),
            PromptInjectionPolicy(sensitivity="low", action="warn"),
            PIIPolicy(
                scan_responses=True,
                action="warn",
                detect=["api_key"],
            ),
        ]

        excluded = set(exclude_policies or [])
        policies = [p for p in policies if p.name not in excluded]

        if override_policies:
            policies.extend(override_policies)

        super().__init__(policies=policies)


__all__ = ["InternalToolsPreset"]

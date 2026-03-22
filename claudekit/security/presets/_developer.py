"""Developer tools security preset.

For: coding assistants, code review tools.
ToolGuardPolicy blocking: "rm -rf*", "sudo rm*", "> /etc/*", "DROP DATABASE*".
PIIPolicy detecting api_key only.
PromptInjectionPolicy(low).
No JailbreakPolicy, no RateLimitPolicy (developers iterate fast).
"""

from __future__ import annotations

from typing import Any, List, Optional

from claudekit.security._layer import SecurityLayer


class DeveloperToolsPreset(SecurityLayer):
    """Pre-configured security for developer tools and coding assistants.

    Minimal friction — protects against dangerous shell commands and API key
    leakage without slowing down developer iteration.

    Parameters
    ----------
    override_policies:
        Additional policies to append.
    exclude_policies:
        Names of built-in policies to remove.

    Example
    -------
    ::

        from claudekit.security.presets import DeveloperToolsPreset

        security = DeveloperToolsPreset()
    """

    def __init__(
        self,
        override_policies: Optional[List[Any]] = None,
        exclude_policies: Optional[List[str]] = None,
    ) -> None:
        from claudekit.security.policies._injection import PromptInjectionPolicy
        from claudekit.security.policies._pii import PIIPolicy
        from claudekit.security.policies._tool_guard import ToolGuardPolicy

        policies: list[Any] = [
            PromptInjectionPolicy(sensitivity="low", action="warn"),
            PIIPolicy(
                scan_responses=True,
                action="warn",
                detect=["api_key"],
            ),
            ToolGuardPolicy(rules={
                "*": [
                    "rm -rf*",
                    "sudo rm*",
                    "> /etc/*",
                    "DROP DATABASE*",
                ],
            }),
        ]

        excluded = set(exclude_policies or [])
        policies = [p for p in policies if p.name not in excluded]

        if override_policies:
            policies.extend(override_policies)

        super().__init__(policies=policies)


__all__ = ["DeveloperToolsPreset"]

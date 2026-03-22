"""Customer-facing security preset.

For: customer support bots, public chat interfaces.
Includes: RateLimitPolicy, BudgetPolicy, PromptInjectionPolicy(medium),
JailbreakPolicy(medium, warn), PIIPolicy(redact SSN/card/API keys),
InputSanitizerPolicy.
"""

from __future__ import annotations

from typing import Any, List, Optional

from claudekit.security._layer import SecurityLayer
from claudekit.security._policy import Policy


class CustomerFacingPreset(SecurityLayer):
    """Pre-configured security for customer-facing applications.

    Bundles rate limiting, budget enforcement, prompt injection detection,
    jailbreak detection, PII redaction, and input sanitisation into a single
    preset that's ready to use out of the box.

    Parameters
    ----------
    max_cost_per_user_usd:
        Per-user cost cap per window. Defaults to ``1.00``.
    window:
        Budget window. Defaults to ``"24h"``.
    override_policies:
        Additional policies to append.
    exclude_policies:
        Names of built-in policies to remove.

    Example
    -------
    ::

        from claudekit.security.presets import CustomerFacingPreset

        security = CustomerFacingPreset(max_cost_per_user_usd=0.50)
    """

    def __init__(
        self,
        max_cost_per_user_usd: float = 1.00,
        window: str = "24h",
        override_policies: Optional[List[Any]] = None,
        exclude_policies: Optional[List[str]] = None,
    ) -> None:
        from claudekit.security.policies._budget import BudgetPolicy
        from claudekit.security.policies._injection import PromptInjectionPolicy
        from claudekit.security.policies._jailbreak import JailbreakPolicy
        from claudekit.security.policies._pii import PIIPolicy
        from claudekit.security.policies._rate_limit import RateLimitPolicy
        from claudekit.security.policies._sanitizer import InputSanitizerPolicy

        policies: list[Any] = [
            RateLimitPolicy(requests_per_minute=60),
            BudgetPolicy(max_cost_usd=max_cost_per_user_usd, window=window),
            PromptInjectionPolicy(sensitivity="medium", action="block"),
            JailbreakPolicy(sensitivity="medium", action="warn"),
            PIIPolicy(
                scan_responses=True,
                action="redact",
                detect=["ssn", "credit_card", "api_key"],
            ),
            InputSanitizerPolicy(),
        ]

        excluded = set(exclude_policies or [])
        policies = [p for p in policies if p.name not in excluded]

        if override_policies:
            policies.extend(override_policies)

        super().__init__(policies=policies)


__all__ = ["CustomerFacingPreset"]

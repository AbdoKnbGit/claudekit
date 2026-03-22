"""Financial services security preset.

For: banking, payments, trading.
Includes everything in CustomerFacingPreset PLUS:
PIIPolicy detecting passport, tax_id, bank_account.
ToolGuardPolicy blocking SQL DELETE and DROP patterns.
Audit hook firing on every security event.
"""

from __future__ import annotations

from typing import Any, List, Optional

from claudekit.security._layer import SecurityLayer


class FinancialServicesPreset(SecurityLayer):
    """Pre-configured security for financial services applications.

    Extends the customer-facing posture with additional PII types,
    SQL injection protection, and stricter tool guarding.

    Parameters
    ----------
    max_cost_per_user_usd:
        Per-user cost cap per window. Defaults to ``0.50``.
    window:
        Budget window. Defaults to ``"24h"``.
    override_policies:
        Additional policies to append.
    exclude_policies:
        Names of built-in policies to remove.

    Example
    -------
    ::

        from claudekit.security.presets import FinancialServicesPreset

        security = FinancialServicesPreset()
    """

    def __init__(
        self,
        max_cost_per_user_usd: float = 0.50,
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
        from claudekit.security.policies._tool_guard import ToolGuardPolicy

        policies: list[Any] = [
            RateLimitPolicy(requests_per_minute=30),
            BudgetPolicy(max_cost_usd=max_cost_per_user_usd, window=window),
            PromptInjectionPolicy(sensitivity="high", action="block"),
            JailbreakPolicy(sensitivity="high", action="block"),
            PIIPolicy(
                scan_responses=True,
                action="block",
                detect=["ssn", "credit_card", "api_key", "passport", "tax_id", "bank_account"],
            ),
            ToolGuardPolicy(rules={
                "*": ["*DELETE*", "*DROP*", "*TRUNCATE*", "*ALTER*"],
            }),
            InputSanitizerPolicy(),
        ]

        excluded = set(exclude_policies or [])
        policies = [p for p in policies if p.name not in excluded]

        if override_policies:
            policies.extend(override_policies)

        super().__init__(policies=policies)


__all__ = ["FinancialServicesPreset"]

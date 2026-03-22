"""Healthcare security preset.

For: medical apps, patient data.
PIIPolicy action="block" (never silently redact health data).
Detects: SSN, passport, phone, email, date_of_birth, medical_record.
PromptInjectionPolicy(high), JailbreakPolicy(high, block).
RateLimitPolicy(5/minute — conservative for PHI).
"""

from __future__ import annotations

from typing import Any, List, Optional

from claudekit.security._layer import SecurityLayer


class HealthcarePreset(SecurityLayer):
    """Pre-configured security for healthcare and patient data applications.

    The strictest preset — blocks rather than redacts PII, uses high-sensitivity
    for injection and jailbreak detection, and applies conservative rate limits.

    Parameters
    ----------
    override_policies:
        Additional policies to append.
    exclude_policies:
        Names of built-in policies to remove.

    Example
    -------
    ::

        from claudekit.security.presets import HealthcarePreset

        security = HealthcarePreset()
    """

    def __init__(
        self,
        override_policies: Optional[List[Any]] = None,
        exclude_policies: Optional[List[str]] = None,
    ) -> None:
        from claudekit.security.policies._injection import PromptInjectionPolicy
        from claudekit.security.policies._jailbreak import JailbreakPolicy
        from claudekit.security.policies._pii import PIIPolicy
        from claudekit.security.policies._rate_limit import RateLimitPolicy

        policies: list[Any] = [
            RateLimitPolicy(requests_per_minute=5),
            PromptInjectionPolicy(sensitivity="high", action="block"),
            JailbreakPolicy(sensitivity="high", action="block"),
            PIIPolicy(
                scan_requests=True,
                scan_responses=True,
                action="block",
                detect=[
                    "ssn", "passport", "phone", "email",
                    "dob", "medical_record",
                ],
            ),
        ]

        excluded = set(exclude_policies or [])
        policies = [p for p in policies if p.name not in excluded]

        if override_policies:
            policies.extend(override_policies)

        super().__init__(policies=policies)


__all__ = ["HealthcarePreset"]

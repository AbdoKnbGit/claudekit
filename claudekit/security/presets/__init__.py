"""Pre-built security presets for common deployment contexts.

Each preset returns a configured :class:`~claudekit.security.SecurityLayer`
with sensible defaults::

    from claudekit.security.presets import CustomerFacingPreset

    security = CustomerFacingPreset(max_cost_per_user_usd=1.00)
"""

from __future__ import annotations

from claudekit.security.presets._customer_facing import CustomerFacingPreset
from claudekit.security.presets._developer import DeveloperToolsPreset
from claudekit.security.presets._financial import FinancialServicesPreset
from claudekit.security.presets._healthcare import HealthcarePreset
from claudekit.security.presets._internal import InternalToolsPreset

__all__ = [
    "CustomerFacingPreset",
    "DeveloperToolsPreset",
    "FinancialServicesPreset",
    "HealthcarePreset",
    "InternalToolsPreset",
]

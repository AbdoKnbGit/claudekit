"""Abstract :class:`Policy` base class and convenience factory methods.

Every security policy inherits from :class:`Policy` and overrides
:meth:`check_request` and/or :meth:`check_response`.  Both methods have
no-op default implementations so that subclasses need only implement the
hook(s) they care about.

The class also exposes ``@classmethod`` factory helpers (e.g.
``Policy.no_prompt_injection()``) that return pre-configured concrete
policy instances -- handy for quick one-liner setups.
"""

from __future__ import annotations

import logging
from abc import ABC
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence

from claudekit.security._context import SecurityContext

if TYPE_CHECKING:
    from claudekit.security.policies._budget import BudgetPolicy
    from claudekit.security.policies._injection import PromptInjectionPolicy
    from claudekit.security.policies._jailbreak import JailbreakPolicy
    from claudekit.security.policies._pii import PIIPolicy
    from claudekit.security.policies._rate_limit import RateLimitPolicy
    from claudekit.security.policies._tool_guard import ToolGuardPolicy

logger = logging.getLogger("claudekit.security")


class Policy(ABC):
    """Base class for all security policies.

    Subclass and override :meth:`check_request` and/or :meth:`check_response`.
    Both have default no-op implementations so concrete policies only need to
    implement the hook(s) relevant to their purpose.

    Attributes
    ----------
    name:
        A short, machine-friendly identifier for this policy instance.
        Used by :class:`~claudekit.security.SecurityLayer` when looking up,
        replacing, or removing policies.
    """

    name: str = "unnamed_policy"

    # ------------------------------------------------------------------ #
    # Hooks
    # ------------------------------------------------------------------ #

    def check_request(
        self,
        messages: List[Dict[str, Any]],
        context: SecurityContext,
    ) -> None:
        """Check a request before it is sent to the model.

        Parameters
        ----------
        messages:
            The list of message dicts (``{"role": ..., "content": ...}``)
            that will be sent to the Claude API.
        context:
            The :class:`SecurityContext` for this request.

        Raises
        ------
        claudekit.errors.SecurityError
            (or a subclass) to block the request.
        """

    def check_response(
        self,
        response: Any,
        context: SecurityContext,
    ) -> Any:
        """Check -- and optionally modify -- a response before returning it.

        Parameters
        ----------
        response:
            The raw API response object (or an intermediate representation).
        context:
            The :class:`SecurityContext` for this request.

        Returns
        -------
        Any
            The (possibly modified) response.  Policies that do not alter
            the response should simply ``return response``.
        """
        return response

    # ------------------------------------------------------------------ #
    # Convenience factory class methods
    # ------------------------------------------------------------------ #

    @classmethod
    def no_prompt_injection(
        cls,
        sensitivity: str = "medium",
        action: str = "block",
        custom_patterns: Optional[List[str]] = None,
    ) -> PromptInjectionPolicy:
        """Create a :class:`PromptInjectionPolicy` with the given settings.

        Parameters
        ----------
        sensitivity:
            ``"low"``, ``"medium"``, or ``"high"``.
        action:
            ``"block"``, ``"warn"``, or ``"sanitize"``.
        custom_patterns:
            Optional list of additional regex patterns to flag.
        """
        from claudekit.security.policies._injection import PromptInjectionPolicy

        return PromptInjectionPolicy(
            sensitivity=sensitivity,
            action=action,
            custom_patterns=custom_patterns,
        )

    @classmethod
    def no_pii_in_output(
        cls,
        action: str = "redact",
        detect: Optional[List[str]] = None,
        redact_with: str = "[REDACTED]",
    ) -> PIIPolicy:
        """Create a :class:`PIIPolicy` focused on response scanning.

        Parameters
        ----------
        action:
            ``"block"``, ``"redact"``, or ``"warn"``.
        detect:
            List of PII types to detect (e.g. ``["ssn", "credit_card"]``).
            Defaults to all types.
        redact_with:
            Replacement string used when *action* is ``"redact"``.
        """
        from claudekit.security.policies._pii import PIIPolicy

        return PIIPolicy(
            scan_requests=False,
            scan_responses=True,
            action=action,
            detect=detect,
            redact_with=redact_with,
        )

    @classmethod
    def max_cost_per_user(
        cls,
        limit_usd: float,
        window: str = "24h",
    ) -> BudgetPolicy:
        """Create a :class:`BudgetPolicy` with a per-user dollar cap.

        Parameters
        ----------
        limit_usd:
            Maximum spend in USD per user within *window*.
        window:
            Time window string: ``"1m"``, ``"1h"``, ``"24h"``, ``"7d"``, or ``"30d"``.
        """
        from claudekit.security.policies._budget import BudgetPolicy

        return BudgetPolicy(max_cost_usd=limit_usd, window=window)

    @classmethod
    def jailbreak_detection(
        cls,
        sensitivity: str = "medium",
        action: str = "block",
    ) -> JailbreakPolicy:
        """Create a :class:`JailbreakPolicy` with the given settings.

        Parameters
        ----------
        sensitivity:
            ``"low"``, ``"medium"``, or ``"high"``.
        action:
            ``"block"`` or ``"warn"``.
        """
        from claudekit.security.policies._jailbreak import JailbreakPolicy

        return JailbreakPolicy(sensitivity=sensitivity, action=action)

    @classmethod
    def block_tool_patterns(
        cls,
        tool_name: str,
        patterns: List[str],
    ) -> ToolGuardPolicy:
        """Create a :class:`ToolGuardPolicy` blocking specific tool inputs.

        Parameters
        ----------
        tool_name:
            The tool whose inputs should be scanned.
        patterns:
            List of regex/glob patterns that should be blocked.
        """
        from claudekit.security.policies._tool_guard import ToolGuardPolicy

        return ToolGuardPolicy(rules={tool_name: patterns})

    @classmethod
    def rate_limit(
        cls,
        requests_per_minute: Optional[int] = None,
        requests_per_hour: Optional[int] = None,
    ) -> RateLimitPolicy:
        """Create a :class:`RateLimitPolicy` with the given limits.

        Parameters
        ----------
        requests_per_minute:
            Maximum requests per minute per user.
        requests_per_hour:
            Maximum requests per hour per user.
        """
        from claudekit.security.policies._rate_limit import RateLimitPolicy

        return RateLimitPolicy(
            requests_per_minute=requests_per_minute,
            requests_per_hour=requests_per_hour,
        )


__all__ = ["Policy"]

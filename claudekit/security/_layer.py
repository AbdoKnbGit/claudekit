"""The :class:`SecurityLayer` orchestrates policy evaluation.

It is the main entry-point that callers interact with.  A
:class:`SecurityLayer` holds an ordered list of :class:`Policy` instances
and runs them sequentially on every request and response.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from claudekit.security._context import SecurityContext
from claudekit.security._policy import Policy

logger = logging.getLogger("claudekit.security")


class SecurityLayer:
    """Ordered policy pipeline applied to every Claude API call.

    Parameters
    ----------
    policies:
        Initial list of :class:`Policy` instances.  Policies are evaluated
        in insertion order -- earlier policies can block before later ones
        run.

    Example
    -------
    ::

        from claudekit.security import SecurityLayer, Policy

        layer = SecurityLayer([
            Policy.no_prompt_injection(sensitivity="high"),
            Policy.no_pii_in_output(),
            Policy.rate_limit(requests_per_minute=30),
        ])

        # Before sending to the API:
        layer.check_request(messages, model="claude-sonnet-4-20250514", user_id="u-123")

        # After receiving a response:
        response = layer.check_response(response, model="claude-sonnet-4-20250514", user_id="u-123")
    """

    def __init__(self, policies: Optional[List[Policy]] = None) -> None:
        self._policies: List[Policy] = list(policies or [])

    # ------------------------------------------------------------------ #
    # Core pipeline
    # ------------------------------------------------------------------ #

    def check_request(
        self,
        messages: List[Dict[str, Any]],
        model: str = "",
        user_id: Optional[str] = None,
        *,
        metadata: Optional[Dict[str, Any]] = None,
        trusted_caller: bool = False,
    ) -> None:
        """Run every policy's :meth:`~Policy.check_request` in order.

        Parameters
        ----------
        messages:
            Message list destined for the Claude API.
        model:
            Model identifier (e.g. ``"claude-sonnet-4-20250514"``).
        user_id:
            Caller-supplied user ID.
        metadata:
            Extra context key/value pairs forwarded to each policy.
        trusted_caller:
            If ``True``, marks the context so injection/jailbreak policies
            can skip their checks.

        Raises
        ------
        claudekit.errors.SecurityError
            If any policy blocks the request.
        """
        ctx = SecurityContext(
            user_id=user_id,
            model=model,
            metadata=metadata or {},
            trusted_caller=trusted_caller,
        )
        logger.debug(
            "SecurityLayer.check_request: %d policies, request_id=%s",
            len(self._policies),
            ctx.request_id,
        )
        for policy in self._policies:
            logger.debug("Running request check: %s", policy.name)
            policy.check_request(messages, ctx)

    def check_response(
        self,
        response: Any,
        model: str = "",
        user_id: Optional[str] = None,
        *,
        metadata: Optional[Dict[str, Any]] = None,
        trusted_caller: bool = False,
    ) -> Any:
        """Run every policy's :meth:`~Policy.check_response` in order.

        Policies may mutate or replace the *response* object (e.g. to redact
        PII).  The value returned from the last policy is the final result.

        Parameters
        ----------
        response:
            Raw API response or intermediate representation.
        model:
            Model identifier.
        user_id:
            Caller-supplied user ID.
        metadata:
            Extra context key/value pairs forwarded to each policy.
        trusted_caller:
            If ``True``, marks the context for trusted-caller bypass.

        Returns
        -------
        Any
            The (possibly modified) response.
        """
        ctx = SecurityContext(
            user_id=user_id,
            model=model,
            metadata=metadata or {},
            trusted_caller=trusted_caller,
        )
        logger.debug(
            "SecurityLayer.check_response: %d policies, request_id=%s",
            len(self._policies),
            ctx.request_id,
        )
        for policy in self._policies:
            logger.debug("Running response check: %s", policy.name)
            response = policy.check_response(response, ctx)
        return response

    # ------------------------------------------------------------------ #
    # Policy management
    # ------------------------------------------------------------------ #

    def add_policy(self, policy: Policy) -> None:
        """Append a policy to the end of the pipeline.

        Parameters
        ----------
        policy:
            The :class:`Policy` instance to add.
        """
        self._policies.append(policy)
        logger.info("Added policy: %s", policy.name)

    def remove_policy(self, name: str) -> None:
        """Remove the first policy whose :attr:`~Policy.name` matches *name*.

        Parameters
        ----------
        name:
            The policy name to look for.

        Raises
        ------
        KeyError
            If no policy with the given name exists.
        """
        for i, policy in enumerate(self._policies):
            if policy.name == name:
                removed = self._policies.pop(i)
                logger.info("Removed policy: %s", removed.name)
                return
        raise KeyError(f"No policy named {name!r} in this SecurityLayer")

    def replace_policy(self, name: str, new_policy: Policy) -> None:
        """Replace the first policy matching *name* with *new_policy*.

        Parameters
        ----------
        name:
            The name of the policy to replace.
        new_policy:
            The replacement :class:`Policy` instance.

        Raises
        ------
        KeyError
            If no policy with the given name exists.
        """
        for i, policy in enumerate(self._policies):
            if policy.name == name:
                self._policies[i] = new_policy
                logger.info(
                    "Replaced policy %s with %s", name, new_policy.name
                )
                return
        raise KeyError(f"No policy named {name!r} in this SecurityLayer")

    @property
    def policies(self) -> List[Policy]:
        """Return a shallow copy of the current policy list."""
        return list(self._policies)

    def __repr__(self) -> str:
        names = [p.name for p in self._policies]
        return f"SecurityLayer(policies={names!r})"


__all__ = ["SecurityLayer"]

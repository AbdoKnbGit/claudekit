"""Base plugin class for the claudekit plugin system.

All hooks are optional -- subclasses override only the hooks they need.
Plugins receive lifecycle events for requests, responses, tool calls,
sessions, costs, errors, and security events.

Example::

    from claudekit.plugins import Plugin

    class MyPlugin(Plugin):
        name = "my_plugin"
        version = "1.0.0"

        def on_request(self, messages, model, context):
            print(f"Request to {model} with {len(messages)} messages")

        def on_error(self, error, context):
            print(f"Error: {error}")
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class Plugin:
    """Base class for claudekit plugins.

    All hooks are optional -- override only the ones you need.  Hooks are
    called by the :class:`~claudekit.plugins.PluginLoader` in the order
    plugins were loaded.

    Attributes
    ----------
    name:
        Plugin identifier.  Should be unique within a loader.
    version:
        Plugin version string following semantic versioning.

    Examples
    --------
    >>> class DebugPlugin(Plugin):
    ...     name = "debug"
    ...     version = "0.1.0"
    ...     def on_request(self, messages, model, context):
    ...         print(f"Sending {len(messages)} messages to {model}")
    """

    name: str = "unnamed_plugin"
    version: str = "0.0.0"

    # ------------------------------------------------------------------ #
    # Request / Response hooks
    # ------------------------------------------------------------------ #

    def on_request(
        self,
        messages: list[dict[str, Any]],
        model: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Called before an API request is sent.

        Parameters
        ----------
        messages:
            The message list being sent to the API.
        model:
            The model identifier.
        context:
            Optional context dict with additional metadata.
        """

    def on_response(
        self,
        response: Any,
        context: dict[str, Any] | None = None,
    ) -> Any:
        """Called after an API response is received.

        Parameters
        ----------
        response:
            The raw API response object.
        context:
            Optional context dict with additional metadata.

        Returns
        -------
        Any
            The response (possibly modified).  Return the original response
            if no modification is needed.
        """
        return response

    # ------------------------------------------------------------------ #
    # Tool hooks
    # ------------------------------------------------------------------ #

    def on_tool_call(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> Any:
        """Called before a tool function is executed.

        Parameters
        ----------
        tool_name:
            Name of the tool being called.
        tool_input:
            Input arguments for the tool.
        context:
            Optional context dict.

        Returns
        -------
        Any
            Return ``None`` to proceed normally.  Return a non-``None`` value
            to short-circuit the tool call and use this as the result.
        """
        return None

    def on_tool_result(
        self,
        tool_name: str,
        result: Any,
        context: dict[str, Any] | None = None,
    ) -> Any:
        """Called after a tool function returns.

        Parameters
        ----------
        tool_name:
            Name of the tool that was called.
        result:
            The return value from the tool.
        context:
            Optional context dict.

        Returns
        -------
        Any
            Return ``None`` to use the original result.  Return a non-``None``
            value to replace the result.
        """
        return None

    # ------------------------------------------------------------------ #
    # Session hooks
    # ------------------------------------------------------------------ #

    def on_session_start(
        self,
        session_name: str,
        config: dict[str, Any] | None = None,
    ) -> None:
        """Called when a session begins.

        Parameters
        ----------
        session_name:
            The session identifier.
        config:
            Optional session configuration dict.
        """

    def on_session_cost_update(
        self,
        session_name: str,
        cost_usd: float,
        usage: dict[str, Any] | None = None,
    ) -> None:
        """Called when session cost is updated.

        Parameters
        ----------
        session_name:
            The session identifier.
        cost_usd:
            Cumulative cost in USD.
        usage:
            Optional token usage breakdown.
        """

    def on_session_end(
        self,
        session_name: str,
        usage: dict[str, Any] | None = None,
    ) -> None:
        """Called when a session ends.

        Parameters
        ----------
        session_name:
            The session identifier.
        usage:
            Optional final usage statistics.
        """

    # ------------------------------------------------------------------ #
    # Error and security hooks
    # ------------------------------------------------------------------ #

    def on_error(
        self,
        error: Exception,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Called when an error occurs.

        Parameters
        ----------
        error:
            The exception that was raised.
        context:
            Optional context dict with additional metadata.
        """

    def on_security_event(
        self,
        event_type: str,
        details: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> None:
        """Called when a security-related event occurs.

        Parameters
        ----------
        event_type:
            Type of security event (e.g. ``"injection_detected"``,
            ``"pii_redacted"``, ``"rate_limited"``).
        details:
            Event-specific details.
        context:
            Optional context dict.
        """

    def __repr__(self) -> str:
        return f"{type(self).__name__}(name={self.name!r}, version={self.version!r})"


__all__ = ["Plugin"]

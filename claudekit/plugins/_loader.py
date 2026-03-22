"""Plugin loader and hook dispatcher.

The :class:`PluginLoader` manages the lifecycle of plugins and dispatches
hook calls to all loaded plugins in registration order.  Its :meth:`load`
method is fluent (returns ``self``), so plugins can be chained::

    loader = (
        PluginLoader()
        .load(LoggingPlugin())
        .load(CostAlertPlugin(threshold_usd=5.0, callback=alert))
    )
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from claudekit.plugins._plugin import Plugin

logger = logging.getLogger(__name__)


class PluginLoader:
    """Manages plugin lifecycle and dispatches hooks to loaded plugins.

    Plugins are called in the order they were loaded.  Hook dispatch methods
    catch and log exceptions from individual plugins so that a failing plugin
    does not break the pipeline.

    Examples
    --------
    >>> loader = PluginLoader()
    >>> loader.load(my_plugin).load(another_plugin)
    >>> loader.dispatch_on_request(messages, model="claude-sonnet-4-6")
    """

    def __init__(self) -> None:
        self._plugins: list[Plugin] = []

    # ------------------------------------------------------------------ #
    # Plugin management
    # ------------------------------------------------------------------ #

    def load(self, plugin: Plugin) -> PluginLoader:
        """Load a plugin into the loader.

        This method is fluent and returns ``self`` for chaining.

        Parameters
        ----------
        plugin:
            The :class:`Plugin` instance to load.

        Returns
        -------
        PluginLoader
            This loader instance (for chaining).
        """
        # Check for duplicate names
        for existing in self._plugins:
            if existing.name == plugin.name:
                logger.warning(
                    "Plugin '%s' is already loaded; replacing with new instance.",
                    plugin.name,
                )
                self._plugins.remove(existing)
                break

        self._plugins.append(plugin)
        logger.info(
            "Loaded plugin '%s' v%s (%d total plugins).",
            plugin.name,
            plugin.version,
            len(self._plugins),
        )
        return self

    def unload(self, name: str) -> None:
        """Unload a plugin by name.

        Parameters
        ----------
        name:
            The name of the plugin to unload.

        Raises
        ------
        KeyError
            If no plugin with the given name is loaded.
        """
        for i, plugin in enumerate(self._plugins):
            if plugin.name == name:
                removed = self._plugins.pop(i)
                logger.info("Unloaded plugin '%s' v%s.", removed.name, removed.version)
                return
        raise KeyError(f"No plugin named {name!r} is loaded")

    def all(self) -> list[Plugin]:
        """Return all loaded plugins.

        Returns
        -------
        list[Plugin]
            A shallow copy of the plugin list in load order.
        """
        return list(self._plugins)

    def get(self, name: str) -> Optional[Plugin]:
        """Look up a loaded plugin by name.

        Parameters
        ----------
        name:
            The plugin name.

        Returns
        -------
        Plugin | None
            The plugin if found, otherwise ``None``.
        """
        for plugin in self._plugins:
            if plugin.name == name:
                return plugin
        return None

    # ------------------------------------------------------------------ #
    # Hook dispatchers
    # ------------------------------------------------------------------ #

    def _safe_call(self, plugin: Plugin, hook_name: str, *args: Any, **kwargs: Any) -> Any:
        """Call a plugin hook, catching and logging exceptions.

        Parameters
        ----------
        plugin:
            The plugin to call.
        hook_name:
            Name of the hook method.
        *args:
            Positional arguments for the hook.
        **kwargs:
            Keyword arguments for the hook.

        Returns
        -------
        Any
            The hook's return value, or ``None`` if an exception was caught.
        """
        try:
            method = getattr(plugin, hook_name)
            return method(*args, **kwargs)
        except (AttributeError, TypeError, ValueError, RuntimeError):
            logger.exception(
                "Plugin '%s' raised an exception in %s.", plugin.name, hook_name
            )
            return None

    def dispatch_on_request(
        self,
        messages: list[dict[str, Any]],
        model: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Dispatch :meth:`~Plugin.on_request` to all loaded plugins.

        Parameters
        ----------
        messages:
            The message list being sent.
        model:
            The model identifier.
        context:
            Optional context dict.
        """
        for plugin in self._plugins:
            self._safe_call(plugin, "on_request", messages, model, context)

    def dispatch_on_response(
        self,
        response: Any,
        context: dict[str, Any] | None = None,
    ) -> Any:
        """Dispatch :meth:`~Plugin.on_response` to all loaded plugins.

        Each plugin may modify or replace the response.  The value returned
        from the last plugin becomes the final response.

        Parameters
        ----------
        response:
            The API response object.
        context:
            Optional context dict.

        Returns
        -------
        Any
            The (possibly modified) response.
        """
        for plugin in self._plugins:
            result = self._safe_call(plugin, "on_response", response, context)
            if result is not None:
                response = result
        return response

    def dispatch_on_tool_call(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> Any:
        """Dispatch :meth:`~Plugin.on_tool_call` to all loaded plugins.

        If any plugin returns a non-``None`` value, that value is returned
        immediately (short-circuiting the actual tool call).

        Parameters
        ----------
        tool_name:
            The tool being called.
        tool_input:
            Input arguments for the tool.
        context:
            Optional context dict.

        Returns
        -------
        Any
            A short-circuit result from a plugin, or ``None`` to proceed.
        """
        for plugin in self._plugins:
            result = self._safe_call(plugin, "on_tool_call", tool_name, tool_input, context)
            if result is not None:
                return result
        return None

    def dispatch_on_tool_result(
        self,
        tool_name: str,
        result: Any,
        context: dict[str, Any] | None = None,
    ) -> Any:
        """Dispatch :meth:`~Plugin.on_tool_result` to all loaded plugins.

        If any plugin returns a non-``None`` value, it replaces the result.

        Parameters
        ----------
        tool_name:
            The tool that was called.
        result:
            The tool's return value.
        context:
            Optional context dict.

        Returns
        -------
        Any
            The (possibly replaced) result.
        """
        for plugin in self._plugins:
            replacement = self._safe_call(
                plugin, "on_tool_result", tool_name, result, context
            )
            if replacement is not None:
                result = replacement
        return result

    def dispatch_on_session_start(
        self,
        session_name: str,
        config: dict[str, Any] | None = None,
    ) -> None:
        """Dispatch :meth:`~Plugin.on_session_start` to all loaded plugins.

        Parameters
        ----------
        session_name:
            The session identifier.
        config:
            Optional session configuration.
        """
        for plugin in self._plugins:
            self._safe_call(plugin, "on_session_start", session_name, config)

    def dispatch_on_session_cost_update(
        self,
        session_name: str,
        cost_usd: float,
        usage: dict[str, Any] | None = None,
    ) -> None:
        """Dispatch :meth:`~Plugin.on_session_cost_update` to all loaded plugins.

        Parameters
        ----------
        session_name:
            The session identifier.
        cost_usd:
            Cumulative cost in USD.
        usage:
            Optional token usage breakdown.
        """
        for plugin in self._plugins:
            self._safe_call(
                plugin, "on_session_cost_update", session_name, cost_usd, usage
            )

    def dispatch_on_session_end(
        self,
        session_name: str,
        usage: dict[str, Any] | None = None,
    ) -> None:
        """Dispatch :meth:`~Plugin.on_session_end` to all loaded plugins.

        Parameters
        ----------
        session_name:
            The session identifier.
        usage:
            Optional final usage statistics.
        """
        for plugin in self._plugins:
            self._safe_call(plugin, "on_session_end", session_name, usage)

    def dispatch_on_error(
        self,
        error: Exception,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Dispatch :meth:`~Plugin.on_error` to all loaded plugins.

        Parameters
        ----------
        error:
            The exception that occurred.
        context:
            Optional context dict.
        """
        for plugin in self._plugins:
            self._safe_call(plugin, "on_error", error, context)

    def dispatch_on_security_event(
        self,
        event_type: str,
        details: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> None:
        """Dispatch :meth:`~Plugin.on_security_event` to all loaded plugins.

        Parameters
        ----------
        event_type:
            Type of security event.
        details:
            Event-specific details.
        context:
            Optional context dict.
        """
        for plugin in self._plugins:
            self._safe_call(
                plugin, "on_security_event", event_type, details, context
            )

    def __len__(self) -> int:
        return len(self._plugins)

    def __repr__(self) -> str:
        names = [p.name for p in self._plugins]
        return f"PluginLoader(plugins={names!r})"


__all__ = ["PluginLoader"]

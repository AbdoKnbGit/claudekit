"""claudekit.plugins -- Lifecycle-hook plugin framework.

Plugins extend claudekit's behaviour without modifying source code.  Subclass
:class:`Plugin` and override the hooks you need::

    from claudekit.plugins import Plugin, PluginLoader

    class MyPlugin(Plugin):
        name = "my_plugin"
        version = "1.0.0"

        def on_response(self, response, context):
            ...
            return response

    loader = PluginLoader()
    loader.load(MyPlugin())

Pre-built plugins
-----------------
- :class:`LoggingPlugin` -- structured logging for all lifecycle events
- :class:`CostAlertPlugin` -- fires a callback when cost exceeds a threshold
- :class:`OpenTelemetryPlugin` -- creates OpenTelemetry tracing spans
"""

from __future__ import annotations

from claudekit.plugins._loader import PluginLoader
from claudekit.plugins._plugin import Plugin
from claudekit.plugins._registry import PluginRegistry


def __getattr__(name: str) -> object:
    """Lazy imports for pre-built plugins."""
    if name == "LoggingPlugin":
        from claudekit.plugins._prebuilt import LoggingPlugin
        return LoggingPlugin
    if name == "CostAlertPlugin":
        from claudekit.plugins._prebuilt import CostAlertPlugin
        return CostAlertPlugin
    if name == "OpenTelemetryPlugin":
        from claudekit.plugins._prebuilt import OpenTelemetryPlugin
        return OpenTelemetryPlugin
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "CostAlertPlugin",
    "LoggingPlugin",
    "OpenTelemetryPlugin",
    "Plugin",
    "PluginLoader",
    "PluginRegistry",
]

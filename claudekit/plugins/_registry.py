"""Named plugin registry for discovery and lookup.

Provides a centralised :class:`PluginRegistry` where plugins can be registered
by name and retrieved later.  This complements the :class:`PluginLoader` by
providing a global discovery mechanism separate from the active plugin pipeline.

Example::

    from claudekit.plugins import Plugin, PluginRegistry

    registry = PluginRegistry()
    registry.register(my_plugin)
    registry.register(another_plugin)

    plugin = registry.get("my_plugin")
    all_plugins = registry.all()
"""

from __future__ import annotations

import logging
from typing import Optional

from claudekit.plugins._plugin import Plugin

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Registry for named plugins.

    Stores plugins by their ``name`` attribute and provides lookup, listing,
    and removal operations.

    Examples
    --------
    >>> registry = PluginRegistry()
    >>> registry.register(my_plugin)
    >>> plugin = registry.get("my_plugin")
    >>> len(registry)
    1
    """

    def __init__(self) -> None:
        self._plugins: dict[str, Plugin] = {}

    def register(self, plugin: Plugin) -> None:
        """Register a plugin, keyed by its ``name``.

        If a plugin with the same name already exists it is replaced and a
        warning is logged.

        Parameters
        ----------
        plugin:
            The :class:`Plugin` to register.
        """
        if plugin.name in self._plugins:
            logger.warning(
                "Replacing existing plugin '%s' in registry.", plugin.name
            )
        self._plugins[plugin.name] = plugin
        logger.debug("Registered plugin '%s' v%s.", plugin.name, plugin.version)

    def get(self, name: str) -> Optional[Plugin]:
        """Look up a plugin by name.

        Parameters
        ----------
        name:
            The plugin name to look up.

        Returns
        -------
        Plugin | None
            The plugin if found, otherwise ``None``.
        """
        return self._plugins.get(name)

    def all(self) -> list[Plugin]:
        """Return all registered plugins.

        Returns
        -------
        list[Plugin]
            A list of all registered plugins in insertion order.
        """
        return list(self._plugins.values())

    def remove(self, name: str) -> None:
        """Remove a plugin from the registry.

        Parameters
        ----------
        name:
            The plugin name to remove.

        Raises
        ------
        KeyError
            If no plugin with the given name is registered.
        """
        if name not in self._plugins:
            raise KeyError(f"No plugin named {name!r} in registry")
        del self._plugins[name]
        logger.debug("Removed plugin '%s' from registry.", name)

    def names(self) -> list[str]:
        """Return the names of all registered plugins.

        Returns
        -------
        list[str]
            Sorted list of registered plugin names.
        """
        return sorted(self._plugins.keys())

    def __len__(self) -> int:
        return len(self._plugins)

    def __contains__(self, name: str) -> bool:
        return name in self._plugins

    def __repr__(self) -> str:
        return f"PluginRegistry(plugins={self.names()!r})"


__all__ = ["PluginRegistry"]

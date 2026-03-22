"""Tool registry for managing collections of tools.

Provides :class:`ToolRegistry`, a named collection of :class:`ToolWrapper`
instances that can be serialised to the format expected by the Anthropic
Messages API or the Claude Agent SDK.

Example::

    from claudekit.tools import tool, ToolRegistry

    @tool
    def greet(name: str) -> str:
        \"\"\"Greet a person by name.

        Args:
            name: The person's name.
        \"\"\"
        return f"Hello, {name}!"

    registry = ToolRegistry("my_tools")
    registry.register(greet)

    # Pass to Anthropic API
    client.messages.create(tools=registry.to_anthropic_format(), ...)
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from claudekit.tools._decorator import ToolWrapper, tool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """A named collection of tools.

    Tools can be registered either as already-decorated :class:`ToolWrapper`
    instances or as plain functions (which will be wrapped automatically).

    Args:
        name: A descriptive name for this registry, used in logging and
            ``repr`` output.
    """

    def __init__(self, name: str = "default") -> None:
        self._name = name
        self._tools: dict[str, ToolWrapper] = {}

    @property
    def name(self) -> str:
        """The registry name."""
        return self._name

    def register(self, tool_or_fn: ToolWrapper | Callable[..., Any]) -> None:
        """Register a tool or plain function.

        If the argument is not already a :class:`ToolWrapper`, it is
        automatically wrapped with the ``@tool`` decorator.

        Args:
            tool_or_fn: Either a ``@tool``-decorated function or a plain
                callable to be auto-wrapped.

        Raises:
            ValueError: If a tool with the same name is already registered.
        """
        if isinstance(tool_or_fn, ToolWrapper):
            wrapper = tool_or_fn
        else:
            wrapper = tool(tool_or_fn)

        if wrapper.name in self._tools:
            raise ValueError(
                f"Tool {wrapper.name!r} is already registered in "
                f"registry {self._name!r}."
            )

        self._tools[wrapper.name] = wrapper
        logger.debug(
            "Registered tool %r in registry %r.", wrapper.name, self._name
        )

    def get(self, name: str) -> ToolWrapper | None:
        """Look up a tool by name.

        Args:
            name: The tool name to look up.

        Returns:
            The :class:`ToolWrapper` if found, ``None`` otherwise.
        """
        return self._tools.get(name)

    def all(self) -> list[ToolWrapper]:
        """Return all registered tools.

        Returns:
            A list of all :class:`ToolWrapper` instances in registration order.
        """
        return list(self._tools.values())

    def to_anthropic_format(self) -> list[dict[str, Any]]:
        """Serialise all tools to the Anthropic Messages API format.

        Returns:
            A list of tool definition dicts ready for the ``tools=`` parameter
            of ``client.messages.create()``.
        """
        return [t.to_dict() for t in self._tools.values()]

    def to_agent_sdk_format(self) -> list[str]:
        """Serialise tool names for the Claude Agent SDK ``allowed_tools`` list.

        Returns:
            A list of tool name strings.
        """
        return list(self._tools.keys())

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __repr__(self) -> str:
        tool_names = list(self._tools.keys())
        return f"<ToolRegistry name={self._name!r} tools={tool_names}>"

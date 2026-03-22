"""claudekit.tools -- Tool decorator, registry, and MCP server builder.

This module provides the core primitives for defining, managing, and serving
tools that Claude can use.

Quick start::

    from claudekit.tools import tool, ToolRegistry, ToolError

    @tool
    def greet(name: str) -> str:
        \"\"\"Greet someone by name.

        Args:
            name: The person's name.
        \"\"\"
        return f"Hello, {name}!"

    registry = ToolRegistry()
    registry.register(greet)

    # Use with the Anthropic API
    client.messages.create(
        model="claude-sonnet-4-6",
        tools=registry.to_anthropic_format(),
        ...
    )
"""

from __future__ import annotations

from claudekit.tools._decorator import ToolWrapper, tool
from claudekit.tools._mcp_server import MCPServer
from claudekit.tools._registry import ToolRegistry
from claudekit.tools._validator import ToolInputValidator

# Re-export ToolError from anthropic SDK if available, otherwise provide fallback
try:
    from anthropic.lib.tools._beta_functions import ToolError
except ImportError:
    class ToolError(Exception):  # type: ignore[no-redef]
        """Fallback ToolError when anthropic is not available."""
        pass

# Re-export ToolInputValidationError for convenience
try:
    from claudekit.errors import ToolInputValidationError
except ImportError:
    # Defensive fallback if errors module isn't fully initialised yet
    from claudekit.errors._codes import TOOL_INPUT_VALIDATION_FAILED

    class ToolInputValidationError(Exception):  # type: ignore[no-redef]
        """Fallback ToolInputValidationError."""

        def __init__(self, tool_name: str, errors: list[dict[str, object]]) -> None:
            super().__init__(
                f"Input validation failed for tool {tool_name!r}: "
                f"{len(errors)} error(s)"
            )
            self.tool_name = tool_name
            self.errors = errors

__all__ = [
    "MCPServer",
    "ToolError",
    "ToolInputValidationError",
    "ToolInputValidator",
    "ToolRegistry",
    "ToolWrapper",
    "tool",
]

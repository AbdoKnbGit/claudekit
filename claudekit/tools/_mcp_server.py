"""MCP (Model Context Protocol) server builder from ``@tool``-decorated functions.

Provides :class:`MCPServer` which wraps one or more :class:`ToolWrapper`
instances into a stdio-based MCP server that Claude can connect to.

Example::

    from claudekit.tools import tool, MCPServer

    @tool
    def add(a: int, b: int) -> str:
        \"\"\"Add two numbers.

        Args:
            a: First number.
            b: Second number.
        \"\"\"
        return str(a + b)

    server = MCPServer("math_server")
    server.add(add)
    server.run()  # blocking stdio server
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Any

from claudekit.tools._decorator import ToolWrapper

logger = logging.getLogger(__name__)


def _require_mcp() -> Any:
    """Lazily import the ``mcp`` package, raising a clear error if absent.

    Returns:
        The ``mcp`` module.

    Raises:
        PlatformNotAvailableError: If the ``mcp`` package is not installed.
    """
    try:
        import mcp  # noqa: F811
        return mcp
    except ImportError:
        from claudekit.errors import PlatformNotAvailableError
        raise PlatformNotAvailableError(
            package="mcp",
            feature="MCP server support",
        )


class MCPServer:
    """Builds and runs a stdio MCP server from ``@tool``-decorated functions.

    The server exposes the registered tools via the Model Context Protocol
    so that Claude (or any MCP-compatible client) can discover and invoke them.

    Args:
        name: A human-readable name for the server.
        version: Server version string.
    """

    def __init__(self, name: str = "claudekit-mcp", version: str = "1.0.0") -> None:
        self._name = name
        self._version = version
        self._tools: list[ToolWrapper] = []

    def add(self, *tools: ToolWrapper) -> None:
        """Register one or more tools with the server.

        Args:
            *tools: :class:`ToolWrapper` instances to expose via MCP.

        Raises:
            TypeError: If any argument is not a :class:`ToolWrapper`.
        """
        for t in tools:
            if not isinstance(t, ToolWrapper):
                raise TypeError(
                    f"Expected a @tool-decorated function (ToolWrapper), "
                    f"got {type(t).__name__!r}. Decorate with @tool first."
                )
            self._tools.append(t)
            logger.debug("Added tool %r to MCP server %r.", t.name, self._name)

    def run(self) -> None:
        """Start the MCP server as a blocking stdio process.

        This method does not return until the server is shut down. It reads
        JSON-RPC messages from stdin and writes responses to stdout.

        Raises:
            PlatformNotAvailableError: If the ``mcp`` package is not installed.
        """
        mcp = _require_mcp()

        from mcp.server import Server
        from mcp.server.stdio import stdio_server
        import mcp.types as mcp_types
        import anyio

        server = Server(self._name)

        # Capture tools for closure
        tool_map: dict[str, ToolWrapper] = {t.name: t for t in self._tools}

        @server.list_tools()
        async def handle_list_tools() -> list[mcp_types.Tool]:
            result = []
            for tw in tool_map.values():
                defn = tw.to_dict()
                result.append(
                    mcp_types.Tool(
                        name=defn["name"],
                        description=defn.get("description", ""),
                        inputSchema=defn["input_schema"],
                    )
                )
            return result

        @server.call_tool()
        async def handle_call_tool(
            name: str, arguments: dict[str, Any]
        ) -> list[mcp_types.TextContent]:
            tw = tool_map.get(name)
            if tw is None:
                raise ValueError(f"Unknown tool: {name!r}")

            import asyncio
            if asyncio.iscoroutinefunction(tw.func):
                result = await tw(**arguments)
            else:
                result = tw(**arguments)

            text = result if isinstance(result, str) else json.dumps(result, default=str)
            return [mcp_types.TextContent(type="text", text=text)]

        async def _run_server() -> None:
            async with stdio_server() as (read_stream, write_stream):
                await server.run(read_stream, write_stream, server.create_initialization_options())

        logger.info("Starting MCP server %r with %d tools.", self._name, len(self._tools))
        anyio.run(_run_server)

    def run_background(self) -> subprocess.Popen[str]:
        """Start the MCP server as a background subprocess.

        Writes a temporary Python script that reconstructs the server and
        launches it via ``subprocess.Popen``.

        Returns:
            A :class:`subprocess.Popen` handle for the background process.

        Raises:
            PlatformNotAvailableError: If the ``mcp`` package is not installed.
        """
        # Verify mcp is available before launching
        _require_mcp()

        # Build a self-contained script that re-creates this server
        tool_defs = []
        for tw in self._tools:
            tool_defs.append({
                "name": tw.name,
                "definition": tw.to_dict(),
                "module": tw.func.__module__,
                "qualname": tw.func.__qualname__,
            })

        script_content = textwrap.dedent(f"""\
            import sys
            import json

            # Re-import the tools and run the server
            sys.path.insert(0, ".")

            from claudekit.tools import MCPServer, tool
            from claudekit.tools._decorator import ToolWrapper

            # Import and reconstruct tools
            tool_infos = {json.dumps(tool_defs)}

            server = MCPServer(name={self._name!r}, version={self._version!r})

            for info in json.loads(tool_infos):
                module_name = info["module"]
                qualname = info["qualname"]

                import importlib
                mod = importlib.import_module(module_name)
                parts = qualname.split(".")
                obj = mod
                for part in parts:
                    obj = getattr(obj, part)

                if isinstance(obj, ToolWrapper):
                    server.add(obj)
                else:
                    wrapped = tool(obj)
                    server.add(wrapped)

            server.run()
        """)

        # Write to a temporary file
        tmp = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            prefix="claudekit_mcp_",
            delete=False,
        )
        tmp.write(script_content)
        tmp.flush()
        tmp.close()

        logger.info(
            "Launching background MCP server %r (script: %s).",
            self._name,
            tmp.name,
        )

        process = subprocess.Popen(
            [sys.executable, tmp.name],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return process

    def to_options_dict(self) -> dict[str, Any]:
        """Generate a configuration dict for ``ClaudeAgentOptions.mcp_servers``.

        Returns:
            A dictionary describing this server's stdio transport configuration,
            suitable for passing to the Claude Agent SDK.
        """
        tool_modules: list[str] = []
        for tw in self._tools:
            mod = tw.func.__module__
            if mod not in tool_modules:
                tool_modules.append(mod)

        return {
            "name": self._name,
            "transport": "stdio",
            "command": sys.executable,
            "args": ["-m", "claudekit.tools._mcp_server", "--name", self._name],
            "tools": [tw.name for tw in self._tools],
            "metadata": {
                "version": self._version,
                "tool_count": len(self._tools),
            },
        }

    def __repr__(self) -> str:
        tool_names = [t.name for t in self._tools]
        return f"<MCPServer name={self._name!r} tools={tool_names}>"

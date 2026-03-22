"""Tool-input guard policy.

:class:`ToolGuardPolicy` inspects tool-use requests (``tool_use`` content
blocks) and blocks or warns when the tool input matches a set of
caller-defined patterns.  This prevents dangerous operations like SQL
injection, destructive shell commands, or unintended file access from
being passed to tool implementations.
"""

from __future__ import annotations

import fnmatch
import logging
import re
import warnings
from typing import Any, Dict, List, Optional

from claudekit.errors._base import ToolBlockedError
from claudekit.security._context import SecurityContext
from claudekit.security._policy import Policy

logger = logging.getLogger("claudekit.security.tool_guard")


def _flatten_input(value: Any, prefix: str = "") -> List[str]:
    """Recursively flatten a dict/list tool input into a list of strings.

    Each leaf value is converted to a string for pattern matching.
    """
    parts: List[str] = []
    if isinstance(value, dict):
        for k, v in value.items():
            parts.extend(_flatten_input(v, prefix=f"{prefix}{k}."))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            parts.extend(_flatten_input(item, prefix=f"{prefix}[{i}]."))
    else:
        parts.append(str(value))
    return parts


class ToolGuardPolicy(Policy):
    """Block tool invocations whose inputs match dangerous patterns.

    Parameters
    ----------
    rules:
        Mapping of tool name to a list of blocked patterns.  Each pattern
        can be a glob (e.g. ``"*DROP TABLE*"``) or a regex (prefixed with
        ``"re:"``).  The pattern is matched against all string-valued fields
        in the tool input dict.

        Example::

            {
                "sql_query": ["*DROP*", "*DELETE FROM*", "re:;\\\\s*--"],
                "shell": ["*rm -rf*", "*sudo*"],
            }

    action:
        ``"block"`` (raise :class:`~claudekit.errors.ToolBlockedError`) or
        ``"warn"`` (emit a :class:`UserWarning`).
    custom_error:
        Optional message override for the error/warning.
    """

    name: str = "tool_guard"

    def __init__(
        self,
        rules: Optional[Dict[str, List[str]]] = None,
        action: str = "block",
        custom_error: Optional[str] = None,
    ) -> None:
        if action not in ("block", "warn"):
            raise ValueError(f"action must be 'block' or 'warn', got {action!r}")
        self.rules: Dict[str, List[str]] = rules or {}
        self.action = action
        self.custom_error = custom_error

        # Pre-compile regex patterns
        self._compiled: Dict[str, List[Any]] = {}
        for tool_name, patterns in self.rules.items():
            compiled: List[Any] = []
            for pat in patterns:
                if pat.startswith("re:"):
                    compiled.append(("regex", re.compile(pat[3:])))
                else:
                    compiled.append(("glob", pat))
            self._compiled[tool_name] = compiled

    # ------------------------------------------------------------------ #
    # Hooks
    # ------------------------------------------------------------------ #

    def check_request(
        self,
        messages: List[Dict[str, Any]],
        context: SecurityContext,
    ) -> None:
        """Scan tool_use content blocks for blocked patterns."""
        for msg in messages:
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") != "tool_use":
                    continue
                tool_name = block.get("name", "")
                tool_input = block.get("input", {})
                self._check_tool(tool_name, tool_input, context)

    def check_response(
        self,
        response: Any,
        context: SecurityContext,
    ) -> Any:
        """Scan model-generated tool_use blocks in the response."""
        content = None
        if isinstance(response, dict):
            content = response.get("content", [])
        else:
            content = getattr(response, "content", None)

        if not isinstance(content, list):
            return response

        for block in content:
            block_type = None
            tool_name = ""
            tool_input: Any = {}

            if isinstance(block, dict):
                block_type = block.get("type")
                tool_name = block.get("name", "")
                tool_input = block.get("input", {})
            else:
                block_type = getattr(block, "type", None)
                tool_name = getattr(block, "name", "")
                tool_input = getattr(block, "input", {})

            if block_type == "tool_use":
                self._check_tool(tool_name, tool_input, context)

        return response

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #

    def _check_tool(
        self,
        tool_name: str,
        tool_input: Any,
        context: SecurityContext,
    ) -> None:
        """Check a single tool invocation against the rules."""
        patterns = self._compiled.get(tool_name)
        if not patterns:
            # Also check for wildcard rules that apply to all tools
            patterns = self._compiled.get("*")
            if not patterns:
                return

        flat_values = _flatten_input(tool_input)

        for value in flat_values:
            for pat_type, pat in patterns:
                matched = False
                if pat_type == "glob":
                    matched = fnmatch.fnmatch(value, pat) or fnmatch.fnmatch(
                        value.lower(), pat.lower()
                    )
                elif pat_type == "regex":
                    matched = bool(pat.search(value))

                if matched:
                    message = (
                        self.custom_error
                        or f"Tool '{tool_name}' input blocked: matched pattern {pat if pat_type == 'glob' else pat.pattern!r}"
                    )
                    logger.warning(
                        "%s (request_id=%s, value=%r)",
                        message,
                        context.request_id,
                        value[:100],
                    )
                    if self.action == "block":
                        raise ToolBlockedError(
                            message,
                            context={
                                "tool_name": tool_name,
                                "matched_value": value[:200],
                                "request_id": context.request_id,
                            },
                        )
                    else:
                        warnings.warn(message, UserWarning, stacklevel=3)
                    return  # One finding per tool invocation is enough


__all__ = ["ToolGuardPolicy"]

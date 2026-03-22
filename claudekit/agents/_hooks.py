"""HookBuilder -- compose Agent SDK hook dictionaries with a fluent API.

Hooks are the primary extension point for controlling agent behaviour at
runtime.  Each helper method on :class:`HookBuilder` returns a plain ``dict``
that can be passed to :class:`~claudekit.agents.AgentRunner` as part of its
``hooks`` list.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class HookBuilder:
    """Factory for Agent SDK hook dictionaries.

    Every method is a static/class-level factory -- there is no mutable state.
    Call methods directly on the class or on an instance; both work identically.

    Examples
    --------
    >>> from claudekit.agents import HookBuilder
    >>> hooks = [
    ...     HookBuilder.block_tool("rm", when=lambda ctx: ctx.get("env") == "prod"),
    ...     HookBuilder.audit_log("/var/log/agent-audit.jsonl"),
    ...     HookBuilder.on_cost_threshold(0.50, lambda cost: print(f"Cost: ${cost}")),
    ... ]
    """

    # ------------------------------------------------------------------ #
    # block_tool
    # ------------------------------------------------------------------ #
    @staticmethod
    def block_tool(
        tool_name: str,
        *,
        when: Optional[Callable[..., bool]] = None,
        message: str = "",
    ) -> dict[str, Any]:
        """Return a hook that blocks a tool invocation.

        Parameters
        ----------
        tool_name:
            Name of the tool to block.
        when:
            Optional predicate ``(context) -> bool``.  When provided, the tool
            is blocked only if the predicate returns ``True``.  If ``None`` the
            tool is blocked unconditionally.
        message:
            Custom message returned to the model when the tool is blocked.

        Returns
        -------
        dict[str, Any]
            A hook dict suitable for passing to the Agent SDK.
        """
        block_message = message or f"Tool '{tool_name}' is blocked by policy."

        def _hook(event: dict[str, Any]) -> Optional[dict[str, Any]]:
            if event.get("type") != "tool_use":
                return None
            if event.get("name") != tool_name:
                return None
            if when is not None and not when(event.get("context", {})):
                return None

            logger.info("HookBuilder.block_tool: blocking '%s'", tool_name)
            return {"type": "tool_result", "blocked": True, "message": block_message}

        return {
            "type": "hook",
            "name": f"block_tool:{tool_name}",
            "callback": _hook,
        }

    # ------------------------------------------------------------------ #
    # allow_only
    # ------------------------------------------------------------------ #
    @staticmethod
    def allow_only(
        tool_name: str,
        patterns: list[str],
    ) -> dict[str, Any]:
        """Return a hook that restricts a tool's input to matching patterns.

        Parameters
        ----------
        tool_name:
            Name of the tool to guard.
        patterns:
            List of allowed input patterns (substring match).  If the tool's
            serialised input does not contain at least one pattern, the call
            is blocked.

        Returns
        -------
        dict[str, Any]
            A hook dict.
        """

        def _hook(event: dict[str, Any]) -> Optional[dict[str, Any]]:
            if event.get("type") != "tool_use":
                return None
            if event.get("name") != tool_name:
                return None

            tool_input = json.dumps(event.get("input", {}), default=str)
            for pattern in patterns:
                if pattern in tool_input:
                    return None  # Allowed

            logger.info(
                "HookBuilder.allow_only: blocking '%s' (input did not match any allowed pattern)",
                tool_name,
            )
            return {
                "type": "tool_result",
                "blocked": True,
                "message": (
                    f"Tool '{tool_name}' input did not match any allowed pattern. "
                    f"Allowed patterns: {patterns}"
                ),
            }

        return {
            "type": "hook",
            "name": f"allow_only:{tool_name}",
            "callback": _hook,
        }

    # ------------------------------------------------------------------ #
    # audit_log
    # ------------------------------------------------------------------ #
    @staticmethod
    def audit_log(path: str, *, include_content: bool = True) -> dict[str, Any]:
        """Return a hook that appends every event to a JSONL audit log.

        Parameters
        ----------
        path:
            File path for the audit log.  Parent directories are created
            automatically.
        include_content:
            Whether to include full tool input/output content.  Set to
            ``False`` for a smaller log that records only event metadata.

        Returns
        -------
        dict[str, Any]
            A hook dict.
        """
        log_path = Path(path)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        def _hook(event: dict[str, Any]) -> None:
            record: dict[str, Any] = {
                "timestamp": time.time(),
                "type": event.get("type", "unknown"),
                "name": event.get("name", ""),
            }
            if include_content:
                record["input"] = event.get("input")
                record["output"] = event.get("output")
                record["content"] = event.get("content")
            else:
                # Metadata only
                record["has_input"] = event.get("input") is not None
                record["has_output"] = event.get("output") is not None

            try:
                with log_path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(record, default=str, ensure_ascii=False) + "\n")
            except OSError:
                logger.exception("HookBuilder.audit_log: failed to write to %s", log_path)

        return {
            "type": "hook",
            "name": f"audit_log:{path}",
            "callback": _hook,
        }

    # ------------------------------------------------------------------ #
    # on_cost_threshold
    # ------------------------------------------------------------------ #
    @staticmethod
    def on_cost_threshold(
        usd: float,
        callback: Callable[[float], Any],
    ) -> dict[str, Any]:
        """Return a hook that fires *callback* when cumulative cost exceeds *usd*.

        Parameters
        ----------
        usd:
            The cost threshold in US dollars.
        callback:
            Called with the current cumulative cost when the threshold is first
            exceeded.  The callback is invoked at most once.

        Returns
        -------
        dict[str, Any]
            A hook dict.
        """
        state: dict[str, Any] = {"fired": False, "cumulative": 0.0}

        def _hook(event: dict[str, Any]) -> None:
            if state["fired"]:
                return

            cost = event.get("cost", event.get("cost_usd", 0.0))
            if cost:
                state["cumulative"] += float(cost)

            if state["cumulative"] >= usd:
                state["fired"] = True
                logger.info(
                    "HookBuilder.on_cost_threshold: $%.4f reached (threshold $%.4f)",
                    state["cumulative"],
                    usd,
                )
                callback(state["cumulative"])

        return {
            "type": "hook",
            "name": f"on_cost_threshold:${usd:.2f}",
            "callback": _hook,
        }

    # ------------------------------------------------------------------ #
    # require_confirmation
    # ------------------------------------------------------------------ #
    @staticmethod
    def require_confirmation(
        tool_name: str,
        *,
        confirm_fn: Optional[Callable[[str, dict[str, Any]], bool]] = None,
    ) -> dict[str, Any]:
        """Return a hook that requires confirmation before a tool executes.

        Parameters
        ----------
        tool_name:
            Name of the tool requiring confirmation.
        confirm_fn:
            A callable ``(tool_name, input) -> bool`` that returns ``True`` to
            allow or ``False`` to block.  If ``None``, the hook defaults to
            an interactive ``input()`` prompt (suitable for CLI usage only).

        Returns
        -------
        dict[str, Any]
            A hook dict.
        """

        def _default_confirm(name: str, tool_input: dict[str, Any]) -> bool:
            """Interactive confirmation via stdin."""
            print(f"\n[HookBuilder] Tool '{name}' wants to run with input:")
            print(f"  {json.dumps(tool_input, default=str, indent=2)[:500]}")
            answer = input("Allow? [y/N] ").strip().lower()
            return answer in ("y", "yes")

        confirmer = confirm_fn or _default_confirm

        def _hook(event: dict[str, Any]) -> Optional[dict[str, Any]]:
            if event.get("type") != "tool_use":
                return None
            if event.get("name") != tool_name:
                return None

            tool_input = event.get("input", {})
            if confirmer(tool_name, tool_input):
                logger.debug("HookBuilder.require_confirmation: '%s' approved", tool_name)
                return None  # Allow

            logger.info("HookBuilder.require_confirmation: '%s' denied by user", tool_name)
            return {
                "type": "tool_result",
                "blocked": True,
                "message": f"Tool '{tool_name}' was denied by the confirmation hook.",
            }

        return {
            "type": "hook",
            "name": f"require_confirmation:{tool_name}",
            "callback": _hook,
        }

    # ------------------------------------------------------------------ #
    # inject_context
    # ------------------------------------------------------------------ #
    @staticmethod
    def inject_context(
        tool_name: str,
        extra: dict[str, Any],
    ) -> dict[str, Any]:
        """Return a hook that injects extra key-value pairs into a tool's input.

        Parameters
        ----------
        tool_name:
            Name of the tool whose input will be augmented.
        extra:
            Dictionary of keys to merge into the tool input before execution.

        Returns
        -------
        dict[str, Any]
            A hook dict.
        """

        def _hook(event: dict[str, Any]) -> Optional[dict[str, Any]]:
            if event.get("type") != "tool_use":
                return None
            if event.get("name") != tool_name:
                return None

            current_input = event.get("input", {})
            if isinstance(current_input, dict):
                merged = {**current_input, **extra}
                logger.debug(
                    "HookBuilder.inject_context: injecting %d keys into '%s'",
                    len(extra),
                    tool_name,
                )
                return {"type": "tool_use_modified", "input": merged}

            logger.warning(
                "HookBuilder.inject_context: tool '%s' input is not a dict; skipping injection",
                tool_name,
            )
            return None

        return {
            "type": "hook",
            "name": f"inject_context:{tool_name}",
            "callback": _hook,
        }

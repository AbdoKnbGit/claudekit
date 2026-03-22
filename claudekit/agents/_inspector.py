"""AgentInspector -- record and visualise every message in an agent run.

The inspector wraps an :class:`~claudekit.agents.AgentRunner` and captures the
full message trace so that developers can debug tool usage, token consumption,
and delegation patterns.
"""

from __future__ import annotations

import json
import logging
import textwrap
import time
from pathlib import Path
from typing import Any, Dict, Optional

from claudekit.agents._runner import AgentResult, AgentRunner

logger = logging.getLogger(__name__)


class AgentInspector:
    """Wraps an :class:`AgentRunner` and records every message for debugging.

    After a run completes the inspector holds the full trace and can render
    it to the terminal, export it as JSON, or return it as a plain dict for
    programmatic analysis.

    Parameters
    ----------
    runner:
        The :class:`AgentRunner` to instrument.

    Examples
    --------
    >>> from claudekit.agents import Agent, AgentRunner, AgentInspector
    >>> agent = Agent(name="demo", model="claude-sonnet-4-6", system="Be helpful.")
    >>> inspector = AgentInspector(AgentRunner(agent))
    >>> result = inspector.run("Explain quantum tunnelling.")
    >>> inspector.print()
    """

    def __init__(self, runner: AgentRunner) -> None:
        self._runner = runner
        self._result: Optional[AgentResult] = None
        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None
        self._messages: list[dict[str, Any]] = []
        self._turn_summaries: list[dict[str, Any]] = []

        logger.debug(
            "AgentInspector wrapping runner for agent '%s'",
            runner.agent.name,
        )

    # ------------------------------------------------------------------ #
    # Run
    # ------------------------------------------------------------------ #
    def run(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResult:
        """Run the wrapped agent and capture the full message trace.

        Parameters
        ----------
        prompt:
            The user prompt / task.
        context:
            Optional context dictionary.

        Returns
        -------
        AgentResult
            The same result the underlying runner would return.
        """
        logger.info("AgentInspector: starting run for agent '%s'", self._runner.agent.name)

        self._start_time = time.monotonic()
        result = self._runner.run(prompt, context=context)
        self._end_time = time.monotonic()
        self._result = result
        self._messages = list(result.messages)
        self._turn_summaries = self._build_turn_summaries(result.messages)

        logger.info(
            "AgentInspector: run complete (%d turns, %d messages captured)",
            result.turns,
            len(self._messages),
        )
        return result

    # ------------------------------------------------------------------ #
    # Print
    # ------------------------------------------------------------------ #
    def print(self, *, max_content_length: int = 200) -> None:
        """Pretty-print the recorded trace to stdout.

        Parameters
        ----------
        max_content_length:
            Maximum characters to show for tool input/output summaries.
        """
        if self._result is None:
            print("[AgentInspector] No run recorded yet. Call .run() first.")
            return

        agent_name = self._runner.agent.name
        sep = "=" * 72
        thin_sep = "-" * 72

        print(sep)
        print(f"  Agent Inspector -- {agent_name!r}")
        print(sep)

        for idx, summary in enumerate(self._turn_summaries, start=1):
            role = summary.get("role", "unknown")
            print(f"\n  Turn {idx}  [{role}]")
            print(f"  {thin_sep}")

            if summary.get("tool_name"):
                print(f"    Tool:   {summary['tool_name']}")
                input_text = _truncate(summary.get("tool_input", ""), max_content_length)
                print(f"    Input:  {input_text}")
                output_text = _truncate(summary.get("tool_output", ""), max_content_length)
                print(f"    Output: {output_text}")

            if summary.get("text"):
                text = _truncate(summary["text"], max_content_length)
                print(f"    Text:   {text}")

            tokens = summary.get("tokens", 0)
            if tokens:
                print(f"    Tokens: {tokens:,}")

        print(f"\n{sep}")
        print(f"  Final output: {_truncate(self._result.output, max_content_length)}")
        print(f"  Turns:        {self._result.turns}")
        print(f"  Tokens:       {self._result.total_tokens:,}")
        print(f"  Cost:         ${self._result.total_cost:.4f}")
        print(f"  Duration:     {self._result.duration_seconds:.2f}s")
        if self._result.session_id:
            print(f"  Session ID:   {self._result.session_id}")
        print(sep)

    # ------------------------------------------------------------------ #
    # Export
    # ------------------------------------------------------------------ #
    def to_dict(self) -> dict[str, Any]:
        """Return the full inspection trace as a plain dictionary.

        Returns
        -------
        dict[str, Any]
            Dictionary containing agent metadata, turn summaries, messages,
            and aggregate metrics.
        """
        if self._result is None:
            return {"error": "No run recorded yet"}

        return {
            "agent": self._runner.agent.name,
            "model": self._runner.agent.model,
            "turns": self._result.turns,
            "total_tokens": self._result.total_tokens,
            "total_cost": self._result.total_cost,
            "duration_seconds": self._result.duration_seconds,
            "session_id": self._result.session_id,
            "output": self._result.output,
            "turn_summaries": self._turn_summaries,
            "messages": self._messages,
        }

    def export_json(self, path: str | Path) -> None:
        """Write the inspection trace to a JSON file.

        Parameters
        ----------
        path:
            File path to write to.  Parent directories are created as needed.
        """
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)

        data = self.to_dict()
        with target.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, default=str)

        logger.info("AgentInspector: trace exported to %s", target)

    # ------------------------------------------------------------------ #
    # Properties
    # ------------------------------------------------------------------ #
    @property
    def result(self) -> Optional[AgentResult]:
        """The :class:`AgentResult` from the last run, or ``None``."""
        return self._result

    @property
    def messages(self) -> list[dict[str, Any]]:
        """Raw messages captured during the last run."""
        return list(self._messages)

    @property
    def turn_summaries(self) -> list[dict[str, Any]]:
        """Per-turn summaries built from the message trace."""
        return list(self._turn_summaries)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _build_turn_summaries(messages: list[Any]) -> list[dict[str, Any]]:
        """Distill raw messages into per-turn summary dicts."""
        summaries: list[dict[str, Any]] = []

        for msg in messages:
            summary: dict[str, Any] = {}

            if isinstance(msg, dict):
                summary["role"] = msg.get("role", "unknown")
                summary["text"] = msg.get("content", msg.get("text", ""))
                summary["tokens"] = msg.get("tokens", msg.get("usage", {}).get("total_tokens", 0))

                # Tool-use detection
                tool_use = msg.get("tool_use") or msg.get("tool_call")
                if tool_use:
                    if isinstance(tool_use, dict):
                        summary["tool_name"] = tool_use.get("name", "")
                        summary["tool_input"] = _safe_json(tool_use.get("input", ""))
                    elif isinstance(tool_use, list):
                        # Multiple tool uses in one turn
                        names = [t.get("name", "") for t in tool_use if isinstance(t, dict)]
                        summary["tool_name"] = ", ".join(names)
                        summary["tool_input"] = _safe_json(tool_use)

                tool_result = msg.get("tool_result") or msg.get("tool_output")
                if tool_result is not None:
                    summary["tool_output"] = _safe_json(tool_result)
            elif hasattr(msg, "role"):
                summary["role"] = getattr(msg, "role", "unknown")
                summary["text"] = getattr(msg, "content", getattr(msg, "text", ""))
                summary["tokens"] = getattr(msg, "tokens", 0)

                if hasattr(msg, "tool_use"):
                    tu = msg.tool_use
                    summary["tool_name"] = getattr(tu, "name", str(tu))
                    summary["tool_input"] = _safe_json(getattr(tu, "input", ""))
                if hasattr(msg, "tool_result"):
                    summary["tool_output"] = _safe_json(msg.tool_result)
            else:
                summary["role"] = "unknown"
                summary["text"] = str(msg)

            summaries.append(summary)

        return summaries


# =========================================================================== #
# Module-level helpers
# =========================================================================== #

def _truncate(text: str, max_length: int) -> str:
    """Truncate *text* to *max_length* characters, appending an ellipsis."""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def _safe_json(obj: Any) -> str:
    """Best-effort JSON serialisation for display."""
    if isinstance(obj, str):
        return obj
    try:
        return json.dumps(obj, default=str, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(obj)

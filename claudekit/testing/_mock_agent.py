"""Mock agent runner for zero-API testing of agent-based workflows.

Provides :class:`MockAgentRunner` — a drop-in replacement for
:class:`~claudekit.agents.AgentRunner` that returns pre-configured
responses without making any API calls.

Example::

    from claudekit.testing import MockAgentRunner

    runner = MockAgentRunner()
    runner.on("summarize this", "Here is the summary.")
    result = runner.run("Please summarize this document.")
    assert result.output == "Here is the summary."
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MockAgentResult:
    """Result from a mock agent run.

    Attributes:
        output: The text output.
        agent_name: Name of the agent that handled the request.
        turns: Number of simulated turns.
        cost: Simulated cost.
        tools_called: List of tool names invoked during the run.
        metadata: Additional metadata.
    """

    output: str = ""
    agent_name: str = ""
    turns: int = 1
    cost: float = 0.0
    tools_called: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class MockAgentRunner:
    """Mock agent runner for zero-API testing.

    Registers expected prompt patterns and their responses. Supports
    tool call simulation, error simulation, and call tracking.

    Args:
        strict: If ``True`` (default), raises on unmatched prompts. If
            ``False``, returns a generic response.

    Example::

        runner = MockAgentRunner()
        runner.on("weather", "It is sunny.", tools_called=["get_weather"])
        result = runner.run("What is the weather?")
        assert result.output == "It is sunny."
        assert result.tools_called == ["get_weather"]
    """

    def __init__(self, strict: bool = True) -> None:
        self._patterns: list[tuple[str, MockAgentResult]] = []
        self._error_patterns: dict[str, Exception] = {}
        self._default_result: MockAgentResult | None = None
        self._strict = strict
        self.calls: list[dict[str, Any]] = []

    def on(
        self,
        pattern: str,
        output: str,
        *,
        agent_name: str = "mock_agent",
        turns: int = 1,
        cost: float = 0.001,
        tools_called: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Register a pattern → result mapping.

        Args:
            pattern: Substring to match against the prompt.
            output: Text output to return.
            agent_name: Simulated agent name.
            turns: Simulated turn count.
            cost: Simulated cost in USD.
            tools_called: List of tool names to report as called.
            metadata: Extra metadata to attach.
        """
        self._patterns.append((pattern, MockAgentResult(
            output=output,
            agent_name=agent_name,
            turns=turns,
            cost=cost,
            tools_called=tools_called or [],
            metadata=metadata or {},
        )))

    def on_error(self, pattern: str, error: Exception) -> None:
        """Register a pattern that raises an error."""
        self._error_patterns[pattern] = error

    def default_reply(self, output: str) -> None:
        """Set a default result for unmatched prompts."""
        self._default_result = MockAgentResult(
            output=output, agent_name="mock_agent"
        )

    def run(
        self,
        prompt: str,
        *,
        agent_name: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> MockAgentResult:
        """Run and return a mock result.

        Args:
            prompt: The user prompt.
            agent_name: Optional agent name override.
            context: Optional context dict.

        Returns:
            A :class:`MockAgentResult` with the matching response.

        Raises:
            RuntimeError: If strict mode is on and no pattern matches.
            Exception: If the prompt matches an error pattern.
        """
        self.calls.append({
            "prompt": prompt,
            "agent_name": agent_name,
            "context": context,
        })

        # Check error patterns
        for pat, error in self._error_patterns.items():
            if pat.lower() in prompt.lower():
                raise error

        # Check text patterns (most recent first)
        for pat, result in reversed(self._patterns):
            if pat.lower() in prompt.lower():
                if agent_name:
                    result = MockAgentResult(
                        output=result.output,
                        agent_name=agent_name,
                        turns=result.turns,
                        cost=result.cost,
                        tools_called=result.tools_called,
                        metadata=result.metadata,
                    )
                return result

        if self._default_result is not None:
            return self._default_result

        if self._strict:
            registered = [p for p, _ in self._patterns]
            raise RuntimeError(
                f"MockAgentRunner: no pattern matches prompt: {prompt!r}\n"
                f"Registered patterns: {registered}"
            )

        return MockAgentResult(output="OK", agent_name=agent_name or "mock_agent")

    @property
    def call_count(self) -> int:
        """Number of calls made to ``run()``."""
        return len(self.calls)

    def assert_called_with(self, prompt_substring: str) -> None:
        """Assert that a call was made with *prompt_substring*."""
        for call in self.calls:
            if prompt_substring.lower() in call["prompt"].lower():
                return
        prompts = [c["prompt"] for c in self.calls]
        raise AssertionError(
            f"Expected a call containing {prompt_substring!r}.\n"
            f"Actual calls: {prompts}"
        )

    def reset(self) -> None:
        """Clear all calls and registered patterns."""
        self.calls.clear()
        self._patterns.clear()
        self._error_patterns.clear()
        self._default_result = None


__all__ = ["MockAgentRunner", "MockAgentResult"]

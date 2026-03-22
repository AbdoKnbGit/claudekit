"""Orchestrator -- manage named agents, route tasks, and handle delegation.

The :class:`Orchestrator` is the central control plane for multi-agent
workflows.  It:

* Maintains a registry of :class:`~claudekit.agents.Agent` definitions.
* Injects a ``delegate_to_agent`` tool so agents can hand off to each other.
* Detects circular delegation (configurable max depth).
* Aggregates cost and token counts across all participating agents.
* Supports parallel task execution with failure isolation.
* Allows agents on different platforms in the same workflow.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, Optional

from claudekit.orchestration._result import OrchestrationResult

logger = logging.getLogger(__name__)

# Default ceiling to prevent runaway orchestrations.
_DEFAULT_MAX_DELEGATION_DEPTH: int = 5


class Orchestrator:
    """Multi-agent orchestrator with routing and delegation support.

    Parameters
    ----------
    router:
        An optional router instance (any object with an async
        ``route(task, agents) -> str`` method).  When provided, the
        orchestrator can auto-select an entry agent if none is specified.
    max_delegation_depth:
        Maximum depth of agent-to-agent delegation before a
        :class:`~claudekit.errors.DelegationLoopError` is raised.
    max_total_cost_usd:
        Hard ceiling on aggregate cost across all agents in a single
        orchestration run.  ``None`` = unlimited.
    runner_kwargs:
        Default keyword arguments forwarded to every
        :class:`~claudekit.agents.AgentRunner` created internally.

    Examples
    --------
    >>> from claudekit.agents import Agent
    >>> from claudekit.orchestration import Orchestrator, RuleRouter
    >>> support = Agent(name="support", system="You handle support.")
    >>> billing = Agent(name="billing", system="You handle billing.")
    >>> orch = Orchestrator(
    ...     router=RuleRouter({"billing": [r"invoice"]}, default="support"),
    ...     max_total_cost_usd=5.0,
    ... )
    >>> orch.register(support)
    >>> orch.register(billing)
    >>> result = await orch.run("Why was I double-charged?", entry_agent="support")
    """

    def __init__(
        self,
        *,
        router: Any = None,
        max_delegation_depth: int = _DEFAULT_MAX_DELEGATION_DEPTH,
        max_total_cost_usd: Optional[float] = None,
        runner_kwargs: Optional[dict[str, Any]] = None,
    ) -> None:
        self._agents: dict[str, Any] = {}  # name -> Agent
        self._router = router
        self._max_delegation_depth = max_delegation_depth
        self._max_total_cost_usd = max_total_cost_usd
        self._runner_kwargs: dict[str, Any] = runner_kwargs or {}

        logger.debug(
            "Orchestrator initialised (max_depth=%d, max_cost=$%s, router=%s)",
            max_delegation_depth,
            max_total_cost_usd,
            type(router).__name__ if router else None,
        )

    # ================================================================== #
    # Agent registry
    # ================================================================== #
    def register(self, agent: Any) -> None:
        """Register an agent definition.

        Parameters
        ----------
        agent:
            An :class:`~claudekit.agents.Agent` instance.

        Raises
        ------
        claudekit.errors.ConfigurationError
            If an agent with the same name is already registered.
        """
        if agent.name in self._agents:
            from claudekit.errors import ConfigurationError

            raise ConfigurationError(
                f"Agent '{agent.name}' is already registered",
                code="CONFIGURATION_ERROR",
                context={"agent": agent.name},
                recovery_hint="Use a unique name or unregister the existing agent first.",
            )

        self._agents[agent.name] = agent
        logger.info("Orchestrator: registered agent '%s' (model=%s)", agent.name, agent.model)

    def unregister(self, name: str) -> None:
        """Remove an agent from the registry.

        Parameters
        ----------
        name:
            Agent name to remove.

        Raises
        ------
        KeyError
            If no agent with that name is registered.
        """
        if name not in self._agents:
            raise KeyError(f"No agent registered with name '{name}'")
        del self._agents[name]
        logger.info("Orchestrator: unregistered agent '%s'", name)

    @property
    def agents(self) -> dict[str, Any]:
        """Read-only view of the agent registry."""
        return dict(self._agents)

    # ================================================================== #
    # Single-task run
    # ================================================================== #
    async def run(
        self,
        task: str,
        entry_agent: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> OrchestrationResult:
        """Run a task through the orchestrator.

        Parameters
        ----------
        task:
            The task description or user prompt.
        entry_agent:
            Name of the agent to start with.  If ``None``, the router is used.
        context:
            Optional context dictionary available to all agents.

        Returns
        -------
        OrchestrationResult
            Aggregated result.

        Raises
        ------
        claudekit.errors.OrchestratorError
            If no entry agent is specified and no router is configured.
        claudekit.errors.DelegationLoopError
            If circular delegation is detected.
        claudekit.errors.BudgetExceededError
            If the total cost ceiling is breached.
        """
        if not self._agents:
            from claudekit.errors import OrchestratorError

            raise OrchestratorError(
                "No agents registered",
                recovery_hint="Call orchestrator.register(agent) before running.",
            )

        # Determine entry point
        if entry_agent is not None:
            if entry_agent not in self._agents:
                from claudekit.errors import OrchestratorError

                raise OrchestratorError(
                    f"Entry agent '{entry_agent}' is not registered",
                    context={"entry_agent": entry_agent, "registered": sorted(self._agents.keys())},
                    recovery_hint="Register the agent or use a registered name.",
                )
            current_agent_name = entry_agent
        elif self._router is not None:
            current_agent_name = await self._router.route(task, self._agents)
        else:
            from claudekit.errors import OrchestratorError

            raise OrchestratorError(
                "No entry_agent specified and no router configured",
                recovery_hint="Pass entry_agent= or configure a router.",
            )

        # Execution loop (handles delegation)
        start = time.monotonic()
        agent_trace: list[dict[str, Any]] = []
        total_cost: float = 0.0
        total_tokens: int = 0
        current_prompt = task
        delegation_chain: list[str] = []
        final_output = ""

        while True:
            # Circular delegation check
            if len(delegation_chain) >= self._max_delegation_depth:
                from claudekit.errors import DelegationLoopError

                raise DelegationLoopError(
                    f"Delegation depth {len(delegation_chain)} exceeds maximum "
                    f"{self._max_delegation_depth}. Chain: {' -> '.join(delegation_chain)}",
                    context={
                        "chain": delegation_chain,
                        "depth": len(delegation_chain),
                        "max_depth": self._max_delegation_depth,
                    },
                    recovery_hint="Review delegation logic or increase max_delegation_depth.",
                )

            # Cost ceiling check
            if self._max_total_cost_usd is not None and total_cost >= self._max_total_cost_usd:
                from claudekit.errors import BudgetExceededError

                raise BudgetExceededError(
                    f"Orchestration cost ${total_cost:.4f} reached ceiling "
                    f"${self._max_total_cost_usd:.4f}",
                    context={
                        "total_cost": total_cost,
                        "ceiling": self._max_total_cost_usd,
                        "chain": delegation_chain,
                    },
                )

            delegation_chain.append(current_agent_name)
            agent_def = self._agents[current_agent_name]

            logger.info(
                "Orchestrator: running agent '%s' (depth=%d)",
                current_agent_name,
                len(delegation_chain),
            )

            # Build runner with delegation tool injected
            result = await self._run_agent(
                agent_def,
                current_prompt,
                context=context,
            )

            # Record trace
            trace_entry: dict[str, Any] = {
                "agent": current_agent_name,
                "prompt": current_prompt[:500],
                "output": result.output[:500],
                "turns": result.turns,
                "tokens": result.total_tokens,
                "cost": result.total_cost,
                "duration_seconds": result.duration_seconds,
                "session_id": result.session_id,
            }
            agent_trace.append(trace_entry)
            total_cost += result.total_cost
            total_tokens += result.total_tokens
            final_output = result.output

            # Check for delegation in messages
            delegation_target = self._extract_delegation(result)
            if delegation_target is None:
                # No delegation -- we are done
                break

            if delegation_target not in self._agents:
                from claudekit.errors import OrchestratorError

                raise OrchestratorError(
                    f"Agent '{current_agent_name}' tried to delegate to "
                    f"unregistered agent '{delegation_target}'",
                    context={
                        "from_agent": current_agent_name,
                        "to_agent": delegation_target,
                        "registered": sorted(self._agents.keys()),
                    },
                    recovery_hint="Register the target agent.",
                )

            # Prepare for next iteration
            delegation_prompt = self._extract_delegation_prompt(result) or current_prompt
            current_agent_name = delegation_target
            current_prompt = delegation_prompt

        elapsed = time.monotonic() - start

        orch_result = OrchestrationResult(
            final_output=final_output,
            agent_trace=agent_trace,
            total_cost=total_cost,
            total_tokens=total_tokens,
            duration_seconds=round(elapsed, 4),
        )
        logger.info(
            "Orchestrator: run complete in %.2fs (agents=%s, cost=$%.4f)",
            elapsed,
            orch_result.agents_used,
            total_cost,
        )
        return orch_result

    # ================================================================== #
    # Parallel run
    # ================================================================== #
    async def run_parallel(
        self,
        tasks: list[dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
    ) -> list[OrchestrationResult]:
        """Run multiple tasks in parallel with failure isolation.

        Each task dict should contain at minimum ``{"task": str}`` and
        optionally ``{"entry_agent": str}``.

        One task failing does **not** cancel the others.  Failures are recorded
        in the corresponding :attr:`OrchestrationResult.errors` dict.

        Parameters
        ----------
        tasks:
            List of task dictionaries.
        context:
            Optional shared context for all tasks.

        Returns
        -------
        list[OrchestrationResult]
            One result per input task, in the same order.

        Examples
        --------
        >>> results = await orch.run_parallel([
        ...     {"task": "Summarise doc A", "entry_agent": "summariser"},
        ...     {"task": "Translate doc B", "entry_agent": "translator"},
        ... ])
        """
        if not tasks:
            return []

        logger.info("Orchestrator: launching %d parallel tasks", len(tasks))
        start = time.monotonic()

        async def _run_one(idx: int, task_spec: dict[str, Any]) -> OrchestrationResult:
            task_str = task_spec.get("task", "")
            entry = task_spec.get("entry_agent")
            try:
                return await self.run(task_str, entry_agent=entry, context=context)
            except Exception as exc:
                logger.error(
                    "Orchestrator: parallel task %d failed: %s",
                    idx,
                    exc,
                )
                elapsed = time.monotonic() - start
                return OrchestrationResult(
                    final_output="",
                    duration_seconds=round(elapsed, 4),
                    errors={idx: exc},
                )

        coros = [_run_one(i, t) for i, t in enumerate(tasks)]
        results = await asyncio.gather(*coros, return_exceptions=False)

        elapsed = time.monotonic() - start
        logger.info("Orchestrator: all %d parallel tasks complete in %.2fs", len(tasks), elapsed)
        return list(results)

    # ================================================================== #
    # Internal helpers
    # ================================================================== #
    async def _run_agent(
        self,
        agent_def: Any,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Create a runner for *agent_def* and execute it.

        The delegation tool is injected automatically so that agents can
        hand off to siblings without the developer wiring it manually.
        """
        from claudekit.agents._runner import AgentRunner

        # Build the delegate_to_agent tool definition
        delegate_tool = self._build_delegate_tool()

        # Inject the delegation tool into a copy of the agent's tool list
        tools = list(agent_def.tools) + [delegate_tool]

        runner = AgentRunner(
            agent_def,
            sdk_kwargs={**self._runner_kwargs, "tools": tools},
        )
        return await runner.run_async(prompt)

    def _build_delegate_tool(self) -> dict[str, Any]:
        """Return a tool definition for ``delegate_to_agent``.

        The tool allows an agent to specify another agent name and a prompt
        to forward.  The orchestrator intercepts the tool result during
        :meth:`_extract_delegation`.
        """
        agent_names = sorted(self._agents.keys())
        return {
            "name": "delegate_to_agent",
            "description": (
                "Delegate the current task (or a sub-task) to another specialist agent. "
                f"Available agents: {', '.join(agent_names)}."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "agent_name": {
                        "type": "string",
                        "description": "Name of the agent to delegate to.",
                        "enum": agent_names,
                    },
                    "prompt": {
                        "type": "string",
                        "description": "The task or prompt to send to the target agent.",
                    },
                },
                "required": ["agent_name", "prompt"],
            },
        }

    @staticmethod
    def _extract_delegation(result: Any) -> Optional[str]:
        """Inspect an :class:`AgentResult` for a ``delegate_to_agent`` tool use.

        Returns the target agent name, or ``None`` if no delegation was requested.
        """
        messages = getattr(result, "messages", [])
        for msg in reversed(messages):
            # Dict-style messages
            if isinstance(msg, dict):
                tool_use = msg.get("tool_use") or msg.get("tool_call")
                if isinstance(tool_use, dict) and tool_use.get("name") == "delegate_to_agent":
                    return tool_use.get("input", {}).get("agent_name")
                if isinstance(tool_use, list):
                    for tu in tool_use:
                        if isinstance(tu, dict) and tu.get("name") == "delegate_to_agent":
                            return tu.get("input", {}).get("agent_name")

                # Content blocks style (Anthropic API)
                content = msg.get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if (
                            isinstance(block, dict)
                            and block.get("type") == "tool_use"
                            and block.get("name") == "delegate_to_agent"
                        ):
                            return block.get("input", {}).get("agent_name")

            # Object-style messages
            elif hasattr(msg, "tool_use"):
                tu = msg.tool_use
                if hasattr(tu, "name") and tu.name == "delegate_to_agent":
                    tool_input = getattr(tu, "input", {})
                    if isinstance(tool_input, dict):
                        return tool_input.get("agent_name")

        return None

    @staticmethod
    def _extract_delegation_prompt(result: Any) -> Optional[str]:
        """Extract the prompt from a ``delegate_to_agent`` tool call, if any."""
        messages = getattr(result, "messages", [])
        for msg in reversed(messages):
            if isinstance(msg, dict):
                tool_use = msg.get("tool_use") or msg.get("tool_call")
                if isinstance(tool_use, dict) and tool_use.get("name") == "delegate_to_agent":
                    return tool_use.get("input", {}).get("prompt")
                if isinstance(tool_use, list):
                    for tu in tool_use:
                        if isinstance(tu, dict) and tu.get("name") == "delegate_to_agent":
                            return tu.get("input", {}).get("prompt")

                content = msg.get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if (
                            isinstance(block, dict)
                            and block.get("type") == "tool_use"
                            and block.get("name") == "delegate_to_agent"
                        ):
                            return block.get("input", {}).get("prompt")

            elif hasattr(msg, "tool_use"):
                tu = msg.tool_use
                if hasattr(tu, "name") and tu.name == "delegate_to_agent":
                    tool_input = getattr(tu, "input", {})
                    if isinstance(tool_input, dict):
                        return tool_input.get("prompt")

        return None

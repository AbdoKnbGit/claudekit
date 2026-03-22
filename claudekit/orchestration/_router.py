"""Router strategies for multi-agent orchestration.

A router decides *which* agent should handle a given task.  Three strategies
are provided out of the box:

* :class:`LLMRouter` -- uses a lightweight Claude model (Haiku) to classify.
* :class:`RuleRouter` -- keyword / regex rules mapping to agent names.
* :class:`ManualRouter` -- the developer supplies a routing function.

All routers implement a common ``route(task, agents) -> str`` interface so
that :class:`~claudekit.orchestration.Orchestrator` can swap strategies
without code changes.
"""

from __future__ import annotations

import abc
import asyncio
import logging
import re
from typing import Any, Callable, Dict, Optional, Sequence

from claudekit._defaults import DEFAULT_FAST_MODEL

logger = logging.getLogger(__name__)


# =========================================================================== #
# Abstract base
# =========================================================================== #
class BaseRouter(abc.ABC):
    """Abstract base for all routing strategies.

    Subclasses must implement :meth:`route`, which takes a task string and a
    mapping of available agent names to their definitions, and returns the name
    of the agent that should handle the task.
    """

    @abc.abstractmethod
    async def route(
        self,
        task: str,
        agents: Dict[str, Any],
    ) -> str:
        """Select an agent name for the given *task*.

        Parameters
        ----------
        task:
            The task description or user prompt.
        agents:
            Mapping of ``{agent_name: Agent}`` for all registered agents.

        Returns
        -------
        str
            The name of the selected agent.

        Raises
        ------
        claudekit.errors.OrchestratorError
            If no suitable agent can be determined.
        """
        ...


# =========================================================================== #
# LLMRouter
# =========================================================================== #
class LLMRouter(BaseRouter):
    """Route tasks by asking a lightweight LLM to classify them.

    By default the router sends a classification prompt to ``claude-haiku-4-5``.
    The model is asked to reply with exactly one agent name from the registered
    set.

    Parameters
    ----------
    model:
        Model identifier for the classifier.  Defaults to ``"claude-haiku-4-5"``.
    system:
        Optional system prompt override.  A sensible default is provided.
    platform:
        Platform for the classifier call (``"anthropic"``, ``"bedrock"``, etc.).
    temperature:
        Sampling temperature for the classification call.

    Examples
    --------
    >>> router = LLMRouter()
    >>> agent_name = await router.route("I need a refund", agents)
    """

    def __init__(
        self,
        *,
        model: str = DEFAULT_FAST_MODEL,
        system: Optional[str] = None,
        platform: str = "anthropic",
        temperature: float = 0.0,
    ) -> None:
        self._model = model
        self._platform = platform
        self._temperature = temperature
        self._system = system or (
            "You are a task router. Given a task and a list of available agents, "
            "reply with ONLY the name of the single best agent to handle the task. "
            "Do not include any other text, explanation, or formatting."
        )
        logger.debug("LLMRouter initialised (model=%s, platform=%s)", model, platform)

    async def route(
        self,
        task: str,
        agents: Dict[str, Any],
    ) -> str:
        """Classify *task* using an LLM and return the best agent name.

        Parameters
        ----------
        task:
            The task description.
        agents:
            Mapping of ``{agent_name: Agent}``.

        Returns
        -------
        str
            Name of the selected agent.

        Raises
        ------
        claudekit.errors.OrchestratorError
            If the LLM returns an unrecognised agent name.
        """
        agent_names = sorted(agents.keys())
        prompt = (
            f"Available agents: {', '.join(agent_names)}\n\n"
            f"Task: {task}\n\n"
            f"Which agent should handle this task? Reply with the agent name only."
        )

        try:
            import claude_agent_sdk  # type: ignore[import-untyped]

            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: claude_agent_sdk.query(  # type: ignore[attr-defined]
                    prompt=prompt,
                    model=self._model,
                    system_prompt=self._system,
                ),
            )
            # Extract text from response
            if isinstance(response, dict):
                chosen = response.get("output", response.get("result", "")).strip()
            elif hasattr(response, "output"):
                chosen = str(response.output).strip()
            else:
                chosen = str(response).strip()
        except ImportError:
            # SDK not available -- fall back to first agent
            logger.warning(
                "LLMRouter: claude_agent_sdk not installed; falling back to first agent"
            )
            chosen = agent_names[0] if agent_names else ""
        except (AttributeError, KeyError, TypeError, ValueError):
            logger.exception("LLMRouter: classification call failed; falling back to first agent")
            chosen = agent_names[0] if agent_names else ""

        # Validate
        if chosen not in agents:
            # Fuzzy match: the LLM might have returned a slightly different casing
            lower_map = {name.lower(): name for name in agents}
            if chosen.lower() in lower_map:
                chosen = lower_map[chosen.lower()]
            else:
                from claudekit.errors import OrchestratorError

                raise OrchestratorError(
                    f"LLMRouter returned unknown agent '{chosen}'. "
                    f"Available: {agent_names}",
                    context={"returned": chosen, "available": agent_names},
                    recovery_hint="Check agent registration or adjust the router system prompt.",
                )

        logger.info("LLMRouter: routed task to agent '%s'", chosen)
        return chosen


# =========================================================================== #
# RuleRouter
# =========================================================================== #
class RuleRouter(BaseRouter):
    """Route tasks using keyword or regex rules.

    Each agent is associated with a list of patterns.  The first agent whose
    pattern matches the task wins.  Rules are evaluated in registration order.

    Parameters
    ----------
    rules:
        Mapping of ``{agent_name: [pattern, ...]}``.  Patterns are compiled
        as case-insensitive regular expressions.
    default:
        Agent name to return when no rule matches.  If ``None`` and no rule
        matches, an :class:`~claudekit.errors.OrchestratorError` is raised.

    Examples
    --------
    >>> router = RuleRouter(
    ...     {"billing": [r"invoice", r"charge", r"refund"], "support": [r"help", r"bug"]},
    ...     default="support",
    ... )
    >>> agent_name = await router.route("I was charged twice", agents)
    """

    def __init__(
        self,
        rules: Dict[str, Sequence[str]],
        *,
        default: Optional[str] = None,
    ) -> None:
        self._rules: list[tuple[str, list[re.Pattern[str]]]] = []
        for agent_name, patterns in rules.items():
            compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
            self._rules.append((agent_name, compiled))

        self._default = default
        logger.debug(
            "RuleRouter initialised with %d agent rules (default=%s)",
            len(self._rules),
            default,
        )

    async def route(
        self,
        task: str,
        agents: Dict[str, Any],
    ) -> str:
        """Match *task* against rules and return the first matching agent.

        Parameters
        ----------
        task:
            The task description.
        agents:
            Mapping of ``{agent_name: Agent}`` (used for validation).

        Returns
        -------
        str
            Name of the selected agent.

        Raises
        ------
        claudekit.errors.OrchestratorError
            If no rule matches and no default is configured.
        """
        for agent_name, patterns in self._rules:
            for pattern in patterns:
                if pattern.search(task):
                    if agent_name not in agents:
                        from claudekit.errors import OrchestratorError

                        raise OrchestratorError(
                            f"RuleRouter matched agent '{agent_name}' but it is not registered",
                            context={"agent": agent_name, "pattern": pattern.pattern},
                            recovery_hint="Register the agent before routing.",
                        )
                    logger.info(
                        "RuleRouter: matched pattern '%s' -> agent '%s'",
                        pattern.pattern,
                        agent_name,
                    )
                    return agent_name

        # No rule matched
        if self._default is not None:
            if self._default not in agents:
                from claudekit.errors import OrchestratorError

                raise OrchestratorError(
                    f"RuleRouter default agent '{self._default}' is not registered",
                    context={"default": self._default},
                    recovery_hint="Register the default agent.",
                )
            logger.info("RuleRouter: no rule matched; using default '%s'", self._default)
            return self._default

        from claudekit.errors import OrchestratorError

        raise OrchestratorError(
            "RuleRouter: no rule matched and no default configured",
            context={"task_preview": task[:200]},
            recovery_hint="Add a matching rule or set a default agent.",
        )


# =========================================================================== #
# ManualRouter
# =========================================================================== #
class ManualRouter(BaseRouter):
    """Route tasks using a developer-supplied function.

    Parameters
    ----------
    route_fn:
        A callable ``(task: str, agents: dict) -> str`` that returns the name
        of the agent that should handle the task.  The function may be sync or
        async.

    Examples
    --------
    >>> router = ManualRouter(lambda task, agents: "support")
    >>> agent_name = await router.route("Any task", agents)
    """

    def __init__(self, route_fn: Callable[..., str]) -> None:
        self._route_fn = route_fn
        logger.debug("ManualRouter initialised with %s", route_fn)

    async def route(
        self,
        task: str,
        agents: Dict[str, Any],
    ) -> str:
        """Delegate routing to the user-supplied function.

        Parameters
        ----------
        task:
            The task description.
        agents:
            Mapping of ``{agent_name: Agent}``.

        Returns
        -------
        str
            Name of the selected agent.

        Raises
        ------
        claudekit.errors.OrchestratorError
            If the function returns an unregistered agent name.
        """
        import asyncio

        if asyncio.iscoroutinefunction(self._route_fn):
            chosen = await self._route_fn(task, agents)
        else:
            chosen = self._route_fn(task, agents)

        if chosen not in agents:
            from claudekit.errors import OrchestratorError

            raise OrchestratorError(
                f"ManualRouter returned unknown agent '{chosen}'",
                context={"returned": chosen, "available": sorted(agents.keys())},
                recovery_hint="Ensure the routing function returns a registered agent name.",
            )

        logger.info("ManualRouter: routed task to agent '%s'", chosen)
        return chosen

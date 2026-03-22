"""claudekit.orchestration -- multi-agent orchestration and routing.

This module manages named :class:`~claudekit.agents.Agent` definitions, routes
tasks to the right agent, handles delegation between agents, and aggregates
results across parallel or sequential runs.

Quick start::

    from claudekit.agents import Agent
    from claudekit.orchestration import Orchestrator, RuleRouter

    support = Agent(name="support", system="You handle support tickets.")
    billing = Agent(name="billing", system="You handle billing questions.")

    orch = Orchestrator(router=RuleRouter({"billing": [r"invoice", r"charge"]}))
    orch.register(support)
    orch.register(billing)

    result = await orch.run("Why was I charged twice?", entry_agent="support")

Submodules
----------
_orchestrator
    The :class:`Orchestrator` class.
_result
    The :class:`OrchestrationResult` dataclass.
_router
    Router strategies: :class:`LLMRouter`, :class:`RuleRouter`, :class:`ManualRouter`.
"""

from __future__ import annotations

from claudekit.orchestration._orchestrator import Orchestrator
from claudekit.orchestration._result import OrchestrationResult
from claudekit.orchestration._router import LLMRouter, ManualRouter, RuleRouter

__all__ = [
    "LLMRouter",
    "ManualRouter",
    "Orchestrator",
    "OrchestrationResult",
    "RuleRouter",
]

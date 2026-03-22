"""claudekit.agents -- Agent definition, execution, inspection, and budget management.

This module provides the core primitives for defining, running, and monitoring
agents built on top of the Claude Agent SDK.

Quick start::

    from claudekit.agents import Agent, AgentRunner, AgentResult

    agent = Agent(name="helper", model="claude-sonnet-4-6", system="You help users.")
    runner = AgentRunner(agent)
    result = runner.run("What is 2 + 2?")
    print(result.output)

Submodules
----------
_agent
    The :class:`Agent` dataclass defining agent identity and configuration.
_runner
    The :class:`AgentRunner` that executes agents via the Agent SDK.
_inspector
    The :class:`AgentInspector` for recording and debugging agent runs.
_budget
    The :class:`BudgetGuard` for enforcing cost and turn limits.
_hooks
    The :class:`HookBuilder` for composing Agent SDK hook dictionaries.
"""

from __future__ import annotations

from claudekit.agents._agent import Agent
from claudekit.agents._budget import BudgetGuard
from claudekit.agents._hooks import HookBuilder
from claudekit.agents._inspector import AgentInspector
from claudekit.agents._runner import AgentResult, AgentRunner

__all__ = [
    "Agent",
    "AgentResult",
    "AgentRunner",
    "AgentInspector",
    "BudgetGuard",
    "HookBuilder",
]

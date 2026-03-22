"""Reusable skill bundles combining prompt, tools, model, and config.

A :class:`Skill` packages everything needed for a single-purpose AI capability
into a portable, composable unit: system prompt, model choice, tools, output
validation, memory, and security.

Skills can be used standalone as a one-shot callable, attached to an
:class:`~claudekit.agents.Agent`, combined with other skills, or subclassed
for custom behaviour.

Example::

    from claudekit.skills import Skill

    summarizer = Skill(
        name="summarizer",
        description="Summarize text concisely.",
        system="You are an expert summarizer. Be concise and accurate.",
        model="claude-haiku-4-5",
    )
    result = await summarizer.run(input="Long document...", client=client)
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional, Type

from pydantic import BaseModel

from claudekit._defaults import DEFAULT_FAST_MODEL

logger = logging.getLogger(__name__)


@dataclass
class Skill:
    """A reusable bundle of system prompt, tools, model, and optional memory/security.

    Skills can be used standalone as a one-shot callable, attached to an Agent,
    combined with other skills, or subclassed for custom behavior.

    Parameters
    ----------
    name:
        Unique skill identifier.
    description:
        Human-readable description of what this skill does.
    system:
        System prompt that defines the skill's behaviour.
    model:
        Model to use (uses parent agent's model if ``None``).
    tools:
        List of ``@tool``-decorated functions available to the skill.
    output_format:
        Pydantic model for structured output validation.
    memory:
        Optional :class:`~claudekit.memory.MemoryStore` for persistence.
    security:
        Optional :class:`~claudekit.security.SecurityLayer` for policy checks.
    max_tokens:
        Maximum output tokens for API calls.

    Examples
    --------
    >>> skill = Skill(name="summarizer", system="Summarize concisely.", model="claude-haiku-4-5")
    >>> result = await skill.run(input="Long document...", client=client)
    """

    name: str = ""
    description: str = ""
    system: str = ""
    model: Optional[str] = None
    tools: list[Any] = field(default_factory=list)
    output_format: Optional[Type[BaseModel]] = None
    memory: Any = None
    security: Any = None
    max_tokens: Optional[int] = None

    async def run(
        self,
        input: str,
        client: Any,
        context: dict[str, Any] | None = None,
    ) -> str | BaseModel:
        """Execute the skill standalone.

        Sends a single-turn request to the Claude API with the skill's
        configured system prompt, model, and tools, then optionally validates
        the response against ``output_format``.

        Parameters
        ----------
        input:
            The input text/prompt for the skill.
        client:
            A :class:`~claudekit.client.TrackedClient` or compatible client.
        context:
            Optional context dict forwarded to security checks.

        Returns
        -------
        str | BaseModel
            Plain text result, or a validated Pydantic model if
            ``output_format`` is set.
        """
        messages = [{"role": "user", "content": input}]
        kwargs: dict[str, Any] = {
            "model": self.model or DEFAULT_FAST_MODEL,
            "max_tokens": self.max_tokens or 4096,
            "messages": messages,
        }
        if self.system:
            kwargs["system"] = self.system
        if self.tools:
            kwargs["tools"] = [
                t.to_dict() if hasattr(t, "to_dict") else t for t in self.tools
            ]

        if self.security:
            self.security.check_request(messages, kwargs["model"])

        logger.debug(
            "Skill '%s' executing with model=%s, max_tokens=%s",
            self.name,
            kwargs["model"],
            kwargs["max_tokens"],
        )

        if asyncio.iscoroutinefunction(getattr(client.messages, "create", None)):
            response = await client.messages.create(**kwargs)
        else:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, lambda: client.messages.create(**kwargs)
            )

        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text += block.text

        if self.security:
            response = self.security.check_response(response, kwargs["model"])

        if self.output_format:
            logger.debug(
                "Skill '%s' validating output against %s",
                self.name,
                self.output_format.__name__,
            )
            # Strip markdown code fences that models sometimes add
            cleaned = re.sub(r"^```(?:json)?\s*\n?", "", text.strip())
            cleaned = re.sub(r"\n?```\s*$", "", cleaned).strip()
            return self.output_format.model_validate_json(cleaned)

        logger.debug("Skill '%s' completed, output length=%d", self.name, len(text))
        return text

    def to_agent(self) -> Any:
        """Convert this skill to an :class:`~claudekit.agents.Agent` definition.

        Returns
        -------
        Agent
            An ``Agent`` instance configured from this skill's fields.
        """
        from claudekit.agents import Agent

        return Agent(
            name=f"skill_{self.name}",
            model=self.model or DEFAULT_FAST_MODEL,
            system=self.system,
            tools=self.tools,
            security=self.security,
            memory=self.memory,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize skill configuration to a plain dictionary.

        Returns
        -------
        dict[str, Any]
            A JSON-serialisable representation of the skill's configuration.
        """
        return {
            "name": self.name,
            "description": self.description,
            "system": self.system,
            "model": self.model,
            "max_tokens": self.max_tokens,
        }

    def __repr__(self) -> str:
        return (
            f"Skill(name={self.name!r}, model={self.model!r}, "
            f"tools={len(self.tools)})"
        )


__all__ = ["Skill"]

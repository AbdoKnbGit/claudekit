"""Pre-built research skill with web search.

Provides :class:`ResearcherSkill`, a ready-to-use skill that uses
:func:`~claudekit.tools.prebuilt.web_search` to find information and returns
structured :class:`Research` output with findings, sources, confidence, and
a summary.

Example::

    from claudekit.skills.prebuilt import ResearcherSkill

    skill = ResearcherSkill()
    result = await skill.run(input="What are the latest trends in AI?", client=client)
    print(result.summary)
    print(result.confidence)  # e.g. 0.85
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional, Type

from pydantic import BaseModel, Field

from claudekit._defaults import DEFAULT_MODEL
from claudekit.skills._skill import Skill

logger = logging.getLogger(__name__)


class ResearchFinding(BaseModel):
    """A single research finding.

    Attributes
    ----------
    claim:
        The factual claim or finding.
    evidence:
        Supporting evidence or context.
    source:
        URL or description of the source, if available.
    """

    claim: str = Field(description="The factual claim or finding.")
    evidence: str = Field(description="Supporting evidence or context.")
    source: Optional[str] = Field(
        default=None, description="URL or description of the source."
    )


class Research(BaseModel):
    """Structured output of a research task.

    Attributes
    ----------
    findings:
        List of individual research findings.
    sources:
        Deduplicated list of source URLs or references consulted.
    confidence:
        Overall confidence in the research results, from 0.0 to 1.0.
    summary:
        Brief natural-language summary of the research.
    """

    findings: list[ResearchFinding] = Field(
        default_factory=list, description="Individual research findings."
    )
    sources: list[str] = Field(
        default_factory=list, description="Source URLs or references."
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0."
    )
    summary: str = Field(description="Brief summary of the research.")


def _get_web_search_tool() -> Any:
    """Lazily import the web_search tool.

    Returns
    -------
    ToolWrapper
        The ``web_search`` tool from :mod:`claudekit.tools.prebuilt`.

    Raises
    ------
    ImportError
        If the web tools module cannot be loaded.
    """
    from claudekit.tools.prebuilt._web import web_search

    return web_search


@dataclass
class ResearcherSkill(Skill):
    """Research skill that uses web search to gather information.

    Uses Claude Sonnet by default for thorough analysis with
    :func:`~claudekit.tools.prebuilt.web_search` for information gathering.
    Returns a :class:`Research` object with findings, sources, confidence, and
    a summary.

    Examples
    --------
    >>> skill = ResearcherSkill()
    >>> result = await skill.run(
    ...     input="What is quantum computing?", client=client
    ... )
    >>> result.confidence
    0.9
    """

    def __post_init__(self) -> None:
        """Initialise research defaults, tools, and system prompt."""
        if not self.name:
            self.name = "researcher"
        if not self.description:
            self.description = "Research a topic using web search and provide structured findings."
        if not self.model:
            self.model = DEFAULT_MODEL

        self.output_format = Research

        # Attach the web_search tool if not already present
        if not self.tools:
            try:
                web_search = _get_web_search_tool()
                self.tools = [web_search]
                logger.debug("ResearcherSkill: web_search tool attached.")
            except ImportError:
                logger.warning(
                    "ResearcherSkill: web_search tool not available. "
                    "The skill will work but without live web search."
                )

        json_schema = json.dumps(Research.model_json_schema(), indent=2)

        self.system = (
            "You are an expert researcher. When given a topic or question, "
            "use the web_search tool to find relevant, up-to-date information.\n\n"
            "After gathering information, synthesise your findings into a "
            "structured JSON response with:\n"
            "1. **findings**: A list of specific findings, each with a claim, "
            "supporting evidence, and source URL.\n"
            "2. **sources**: A deduplicated list of all source URLs consulted.\n"
            "3. **confidence**: Your overall confidence in the findings (0.0 to 1.0).\n"
            "4. **summary**: A concise summary of the research results.\n\n"
            "Be thorough but concise. Cite sources accurately. "
            "Respond with ONLY a valid JSON object matching this schema. "
            "Do not include markdown code fences, explanations, or any text "
            "outside the JSON object.\n\n"
            f"JSON Schema:\n{json_schema}"
        )

        logger.debug("ResearcherSkill initialised: model=%s", self.model)

    def __repr__(self) -> str:
        return f"ResearcherSkill(name={self.name!r}, model={self.model!r})"


__all__ = ["Research", "ResearchFinding", "ResearcherSkill"]

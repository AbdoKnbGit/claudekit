"""Pre-built summarization skill.

Provides :class:`SummarizerSkill`, a ready-to-use skill that summarises text
in different styles (bullet points, paragraphs, or executive summary).

Example::

    from claudekit.skills.prebuilt import SummarizerSkill

    skill = SummarizerSkill(style="bullet", max_length=200)
    result = await skill.run(input="Long article text...", client=client)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Literal, Optional, Type

from pydantic import BaseModel

from claudekit._defaults import DEFAULT_FAST_MODEL
from claudekit.skills._skill import Skill

logger = logging.getLogger(__name__)

_STYLE_INSTRUCTIONS = {
    "bullet": (
        "Summarize the following text as a concise bulleted list. "
        "Use '-' for each bullet point. Focus on the key points."
    ),
    "paragraph": (
        "Summarize the following text in one or two concise paragraphs. "
        "Capture the main ideas and essential details."
    ),
    "executive": (
        "Write an executive summary of the following text. "
        "Start with the key conclusion, then provide supporting points. "
        "Keep it suitable for a busy executive who needs the essentials quickly."
    ),
}


@dataclass
class SummarizerSkill(Skill):
    """Summarization skill with configurable style and length.

    Produces summaries in bullet-point, paragraph, or executive-summary
    format. Uses Claude Haiku by default for fast, cost-effective summarisation.

    Parameters
    ----------
    max_length:
        Approximate maximum character count for the summary. The model is
        instructed to stay within this limit. Defaults to ``500``.
    style:
        Output format: ``"bullet"``, ``"paragraph"``, or ``"executive"``.
        Defaults to ``"paragraph"``.

    Examples
    --------
    >>> skill = SummarizerSkill(style="bullet", max_length=200)
    >>> result = await skill.run(input="Long article...", client=client)
    """

    max_length: int = 500
    style: Literal["bullet", "paragraph", "executive"] = "paragraph"

    def __post_init__(self) -> None:
        """Initialise default fields after dataclass construction."""
        if not self.name:
            self.name = "summarizer"
        if not self.description:
            self.description = f"Summarize text ({self.style} style, ~{self.max_length} chars)."
        if not self.model:
            self.model = DEFAULT_FAST_MODEL

        style_instruction = _STYLE_INSTRUCTIONS.get(self.style, _STYLE_INSTRUCTIONS["paragraph"])
        self.system = (
            f"{style_instruction}\n\n"
            f"Keep the summary under approximately {self.max_length} characters. "
            "Be accurate and do not fabricate information."
        )

        logger.debug(
            "SummarizerSkill initialised: style=%s, max_length=%d, model=%s",
            self.style,
            self.max_length,
            self.model,
        )

    def __repr__(self) -> str:
        return (
            f"SummarizerSkill(name={self.name!r}, style={self.style!r}, "
            f"max_length={self.max_length}, model={self.model!r})"
        )


__all__ = ["SummarizerSkill"]

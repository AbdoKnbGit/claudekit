"""Pre-built code review skill.

Provides :class:`CodeReviewerSkill`, a ready-to-use skill that analyses source
code and returns a structured :class:`CodeReview` result with issues,
suggestions, a numeric rating, and a summary.

Example::

    from claudekit.skills.prebuilt import CodeReviewerSkill

    skill = CodeReviewerSkill()
    result = await skill.run(input="def add(a, b): return a + b", client=client)
    print(result.rating)     # 4
    print(result.summary)    # "Simple, correct addition function..."
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


class CodeReviewIssue(BaseModel):
    """A single issue found during code review.

    Attributes
    ----------
    severity:
        Severity level: ``"critical"``, ``"warning"``, or ``"info"``.
    line:
        Line number where the issue was found, or ``None`` if not applicable.
    description:
        Human-readable description of the issue.
    """

    severity: str = Field(description="Severity: 'critical', 'warning', or 'info'.")
    line: Optional[int] = Field(default=None, description="Line number, if applicable.")
    description: str = Field(description="Description of the issue.")


class CodeReviewSuggestion(BaseModel):
    """A suggestion for improving the reviewed code.

    Attributes
    ----------
    description:
        What to change and why.
    code:
        Optional replacement code snippet.
    """

    description: str = Field(description="What to change and why.")
    code: Optional[str] = Field(default=None, description="Suggested replacement code.")


class CodeReview(BaseModel):
    """Structured output of a code review.

    Attributes
    ----------
    issues:
        List of issues found in the code.
    suggestions:
        List of improvement suggestions.
    rating:
        Overall code quality rating from 1 (poor) to 5 (excellent).
    summary:
        Brief natural-language summary of the review.
    """

    issues: list[CodeReviewIssue] = Field(
        default_factory=list, description="Issues found in the code."
    )
    suggestions: list[CodeReviewSuggestion] = Field(
        default_factory=list, description="Improvement suggestions."
    )
    rating: int = Field(ge=1, le=5, description="Quality rating from 1 to 5.")
    summary: str = Field(description="Brief summary of the review.")


@dataclass
class CodeReviewerSkill(Skill):
    """Code review skill that produces structured feedback.

    Uses Claude Sonnet by default for thorough analysis.  Returns a
    :class:`CodeReview` object with issues, suggestions, a 1--5 rating, and
    a summary.

    Examples
    --------
    >>> skill = CodeReviewerSkill()
    >>> review = await skill.run(input="def f(x): return x+1", client=client)
    >>> review.rating
    4
    >>> review.summary
    'Simple function with...'
    """

    def __post_init__(self) -> None:
        """Initialise code review defaults and system prompt."""
        if not self.name:
            self.name = "code_reviewer"
        if not self.description:
            self.description = "Review code and provide structured feedback."
        if not self.model:
            self.model = DEFAULT_MODEL

        self.output_format = CodeReview

        json_schema = json.dumps(CodeReview.model_json_schema(), indent=2)

        self.system = (
            "You are an expert code reviewer. Analyse the provided code and "
            "return a structured JSON review.\n\n"
            "Your review must include:\n"
            "1. **issues**: A list of problems found (severity: 'critical', "
            "'warning', or 'info'; optional line number; description).\n"
            "2. **suggestions**: A list of improvement suggestions (description "
            "and optional replacement code).\n"
            "3. **rating**: An integer from 1 (poor) to 5 (excellent) reflecting "
            "overall code quality.\n"
            "4. **summary**: A brief natural-language summary of your review.\n\n"
            "Respond with ONLY a valid JSON object matching this schema. "
            "Do not include markdown code fences, explanations, or any text "
            "outside the JSON object.\n\n"
            f"JSON Schema:\n{json_schema}"
        )

        logger.debug(
            "CodeReviewerSkill initialised: model=%s", self.model
        )

    def __repr__(self) -> str:
        return f"CodeReviewerSkill(name={self.name!r}, model={self.model!r})"


__all__ = ["CodeReview", "CodeReviewIssue", "CodeReviewSuggestion", "CodeReviewerSkill"]

"""Pre-built skills ready for immediate use.

This package provides production-ready skill implementations that work with
zero configuration.  Each skill can be used standalone, attached to an
:class:`~claudekit.agents.Agent`, or registered with a
:class:`~claudekit.skills.SkillRegistry`.

Available skills:

- :class:`SummarizerSkill` -- Summarize text in bullet, paragraph, or
  executive style.
- :class:`ClassifierSkill` -- Classify text into one of a given set of
  categories with automatic retry.
- :class:`DataExtractorSkill` -- Extract structured data using a Pydantic
  schema.
- :class:`CodeReviewerSkill` -- Review code and return structured feedback
  with issues, suggestions, and a rating.
- :class:`ResearcherSkill` -- Research a topic using web search and return
  structured findings.

Example::

    from claudekit.skills.prebuilt import SummarizerSkill, ClassifierSkill

    summarizer = SummarizerSkill(style="bullet")
    classifier = ClassifierSkill(categories=["positive", "negative", "neutral"])
"""

from __future__ import annotations

from claudekit.skills.prebuilt._classifier import ClassifierSkill
from claudekit.skills.prebuilt._extractor import DataExtractorSkill
from claudekit.skills.prebuilt._researcher import Research, ResearchFinding, ResearcherSkill
from claudekit.skills.prebuilt._reviewer import (
    CodeReview,
    CodeReviewIssue,
    CodeReviewSuggestion,
    CodeReviewerSkill,
)
from claudekit.skills.prebuilt._summarizer import SummarizerSkill

__all__ = [
    "ClassifierSkill",
    "CodeReview",
    "CodeReviewIssue",
    "CodeReviewSuggestion",
    "CodeReviewerSkill",
    "DataExtractorSkill",
    "Research",
    "ResearchFinding",
    "ResearcherSkill",
    "SummarizerSkill",
]

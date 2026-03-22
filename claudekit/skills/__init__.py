"""claudekit.skills -- Reusable skill bundles for Claude agents.

A *skill* packages a system prompt, model choice, tools, output validation,
memory, and security into a single portable, composable unit.  Skills can be
used standalone, attached to an :class:`~claudekit.agents.Agent`, combined
with other skills, or subclassed for custom behaviour.

Quick start::

    from claudekit.skills import Skill, SkillRegistry

    # Create a custom skill
    summarizer = Skill(
        name="summarizer",
        system="Summarize concisely.",
        model="claude-haiku-4-5",
    )
    result = await summarizer.run(input="Long text...", client=client)

    # Or use a pre-built skill
    from claudekit.skills import SummarizerSkill
    skill = SummarizerSkill(style="bullet", max_length=200)

Submodules
----------
_skill
    The :class:`Skill` dataclass -- the core abstraction.
_registry
    The :class:`SkillRegistry` for named skill lookup.
prebuilt
    Production-ready skill implementations:
    :class:`SummarizerSkill`, :class:`ClassifierSkill`,
    :class:`DataExtractorSkill`, :class:`CodeReviewerSkill`,
    :class:`ResearcherSkill`.
"""

from __future__ import annotations

from claudekit.skills._registry import SkillRegistry
from claudekit.skills._skill import Skill
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
    # Core
    "Skill",
    "SkillRegistry",
    # Pre-built skills
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

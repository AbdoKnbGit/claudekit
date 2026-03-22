"""Named skill registry for discovery and lookup.

Provides a centralised :class:`SkillRegistry` where skills can be registered
by name and retrieved later.  This is useful for applications that need to
discover skills dynamically or compose them at runtime.

Example::

    from claudekit.skills import Skill, SkillRegistry

    registry = SkillRegistry()
    registry.register(Skill(name="summarizer", system="Summarize concisely."))
    registry.register(Skill(name="classifier", system="Classify inputs."))

    skill = registry.get("summarizer")
    all_skills = registry.all()
"""

from __future__ import annotations

import logging
from typing import Optional

from claudekit.skills._skill import Skill

logger = logging.getLogger(__name__)


class SkillRegistry:
    """Registry for named skills.

    Stores skills by their ``name`` attribute and provides lookup, listing,
    and removal operations.

    Examples
    --------
    >>> registry = SkillRegistry()
    >>> registry.register(summarizer_skill)
    >>> skill = registry.get("summarizer")
    >>> len(registry)
    1
    """

    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        """Register a skill, keyed by its ``name``.

        If a skill with the same name already exists it is replaced and a
        warning is logged.

        Parameters
        ----------
        skill:
            The :class:`Skill` to register.
        """
        if skill.name in self._skills:
            logger.warning(
                "Replacing existing skill '%s' in registry.", skill.name
            )
        self._skills[skill.name] = skill
        logger.debug("Registered skill '%s'.", skill.name)

    def get(self, name: str) -> Optional[Skill]:
        """Look up a skill by name.

        Parameters
        ----------
        name:
            The skill name to look up.

        Returns
        -------
        Skill | None
            The skill if found, otherwise ``None``.
        """
        return self._skills.get(name)

    def all(self) -> list[Skill]:
        """Return all registered skills.

        Returns
        -------
        list[Skill]
            A list of all registered skills in insertion order.
        """
        return list(self._skills.values())

    def remove(self, name: str) -> None:
        """Remove a skill from the registry.

        Parameters
        ----------
        name:
            The skill name to remove.

        Raises
        ------
        KeyError
            If no skill with the given name is registered.
        """
        if name not in self._skills:
            raise KeyError(f"No skill named {name!r} in registry")
        del self._skills[name]
        logger.debug("Removed skill '%s' from registry.", name)

    def names(self) -> list[str]:
        """Return the names of all registered skills.

        Returns
        -------
        list[str]
            Sorted list of registered skill names.
        """
        return sorted(self._skills.keys())

    def __len__(self) -> int:
        return len(self._skills)

    def __contains__(self, name: str) -> bool:
        return name in self._skills

    def __repr__(self) -> str:
        return f"SkillRegistry(skills={self.names()!r})"


__all__ = ["SkillRegistry"]

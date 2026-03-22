"""Pre-built classification skill.

Provides :class:`ClassifierSkill`, a ready-to-use skill that classifies input
text into one of a given set of categories.  Automatically retries (up to 2
times) if the model returns a value outside the allowed categories.

Example::

    from claudekit.skills.prebuilt import ClassifierSkill

    skill = ClassifierSkill(categories=["positive", "negative", "neutral"])
    result = await skill.run(input="I love this product!", client=client)
    print(result)  # "positive"
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional, Type

from pydantic import BaseModel

from claudekit._defaults import DEFAULT_FAST_MODEL
from claudekit.skills._skill import Skill

logger = logging.getLogger(__name__)

_MAX_RETRIES = 2


@dataclass
class ClassifierSkill(Skill):
    """Classification skill that maps input text to a fixed set of categories.

    The skill instructs the model to respond with exactly one of the provided
    category labels.  If the model returns an invalid category, the skill
    retries up to :data:`_MAX_RETRIES` times with increasingly explicit
    instructions.

    Parameters
    ----------
    categories:
        List of allowed category labels.  Must contain at least two items.

    Raises
    ------
    ValueError
        If ``categories`` has fewer than two items.

    Examples
    --------
    >>> skill = ClassifierSkill(categories=["spam", "ham"])
    >>> result = await skill.run(input="Buy now! Limited offer!", client=client)
    >>> result
    'spam'
    """

    categories: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Initialise defaults and validate categories."""
        if len(self.categories) < 2:
            raise ValueError(
                f"ClassifierSkill requires at least 2 categories, got {len(self.categories)}"
            )

        if not self.name:
            self.name = "classifier"
        if not self.description:
            self.description = f"Classify text into one of: {', '.join(self.categories)}."
        if not self.model:
            self.model = DEFAULT_FAST_MODEL

        categories_str = ", ".join(f'"{c}"' for c in self.categories)
        self.system = (
            "You are a precise text classifier. Your task is to classify the "
            "given text into exactly one of the following categories:\n\n"
            f"  {categories_str}\n\n"
            "Respond with ONLY the category label, nothing else. "
            "Do not include quotes, punctuation, or explanation."
        )

        logger.debug(
            "ClassifierSkill initialised: categories=%s, model=%s",
            self.categories,
            self.model,
        )

    async def run(
        self,
        input: str,
        client: Any,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Classify the input text, retrying on invalid responses.

        Parameters
        ----------
        input:
            The text to classify.
        client:
            A :class:`~claudekit.client.TrackedClient` or compatible client.
        context:
            Optional context dict forwarded to security checks.

        Returns
        -------
        str
            One of the configured category labels.

        Raises
        ------
        ValueError
            If the model fails to return a valid category after all retries.
        """
        categories_lower = {c.lower(): c for c in self.categories}
        attempt = 0
        last_response = ""

        while attempt <= _MAX_RETRIES:
            if attempt == 0:
                prompt = input
            else:
                categories_str = ", ".join(f'"{c}"' for c in self.categories)
                prompt = (
                    f"Previous response '{last_response}' was not a valid category. "
                    f"You MUST respond with exactly one of: {categories_str}\n\n"
                    f"Text to classify: {input}"
                )

            logger.debug(
                "ClassifierSkill attempt %d/%d for input (length=%d)",
                attempt + 1,
                _MAX_RETRIES + 1,
                len(input),
            )

            result = await super().run(input=prompt, client=client, context=context)
            if not isinstance(result, str):
                result = str(result)

            cleaned = result.strip().strip('"').strip("'").strip()

            # Exact match
            if cleaned in self.categories:
                logger.debug("ClassifierSkill matched category: %s", cleaned)
                return cleaned

            # Case-insensitive match
            if cleaned.lower() in categories_lower:
                matched = categories_lower[cleaned.lower()]
                logger.debug(
                    "ClassifierSkill matched category (case-insensitive): %s -> %s",
                    cleaned,
                    matched,
                )
                return matched

            last_response = cleaned
            attempt += 1
            logger.warning(
                "ClassifierSkill invalid response '%s' on attempt %d",
                cleaned,
                attempt,
            )

        raise ValueError(
            f"ClassifierSkill failed to produce a valid category after "
            f"{_MAX_RETRIES + 1} attempts. Last response: {last_response!r}. "
            f"Valid categories: {self.categories}"
        )

    def __repr__(self) -> str:
        return (
            f"ClassifierSkill(name={self.name!r}, "
            f"categories={self.categories!r}, model={self.model!r})"
        )


__all__ = ["ClassifierSkill"]

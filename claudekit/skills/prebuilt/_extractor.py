"""Pre-built data extraction skill.

Provides :class:`DataExtractorSkill`, a ready-to-use skill that extracts
structured data from unstructured text using a Pydantic schema for validation.

Example::

    from pydantic import BaseModel
    from claudekit.skills.prebuilt import DataExtractorSkill

    class Contact(BaseModel):
        name: str
        email: str
        phone: str | None = None

    skill = DataExtractorSkill(schema=Contact)
    result = await skill.run(
        input="John Smith, john@example.com, (555) 123-4567",
        client=client,
    )
    print(result.name)   # "John Smith"
    print(result.email)  # "john@example.com"
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional, Type

from pydantic import BaseModel

from claudekit._defaults import DEFAULT_FAST_MODEL
from claudekit.skills._skill import Skill

logger = logging.getLogger(__name__)


def _schema_to_description(schema_class: Type[BaseModel]) -> str:
    """Generate a human-readable field description from a Pydantic model.

    Parameters
    ----------
    schema_class:
        The Pydantic model class to describe.

    Returns
    -------
    str
        A formatted string listing each field, its type, and whether it is
        required or optional.
    """
    schema = schema_class.model_json_schema()
    properties = schema.get("properties", {})
    required_fields = set(schema.get("required", []))
    lines: list[str] = []

    for name, prop in properties.items():
        field_type = prop.get("type", "any")
        req_label = "required" if name in required_fields else "optional"
        description = prop.get("description", "")
        desc_suffix = f" - {description}" if description else ""
        lines.append(f"  - {name} ({field_type}, {req_label}){desc_suffix}")

    return "\n".join(lines)


@dataclass
class DataExtractorSkill(Skill):
    """Structured data extraction skill using Pydantic validation.

    Given a Pydantic model class as the ``schema``, this skill instructs
    the model to return a JSON object matching that schema.  The response is
    then validated and returned as a Pydantic model instance.

    Parameters
    ----------
    schema:
        A Pydantic :class:`~pydantic.BaseModel` subclass defining the
        expected output structure.

    Raises
    ------
    ValueError
        If ``schema`` is not provided.

    Examples
    --------
    >>> class Invoice(BaseModel):
    ...     vendor: str
    ...     total: float
    ...     currency: str = "USD"
    >>> skill = DataExtractorSkill(schema=Invoice)
    >>> result = await skill.run(input="Invoice from Acme: $42.50", client=client)
    >>> result.total
    42.5
    """

    schema: Optional[Type[BaseModel]] = None

    def __post_init__(self) -> None:
        """Initialise defaults and build the extraction system prompt."""
        if self.schema is None:
            raise ValueError("DataExtractorSkill requires a 'schema' parameter.")

        if not self.name:
            self.name = f"extractor_{self.schema.__name__.lower()}"
        if not self.description:
            self.description = f"Extract {self.schema.__name__} data from text."
        if not self.model:
            self.model = DEFAULT_FAST_MODEL

        # Set the output_format for parent validation
        self.output_format = self.schema

        field_desc = _schema_to_description(self.schema)
        json_schema = json.dumps(self.schema.model_json_schema(), indent=2)

        self.system = (
            "You are a precise data extraction assistant. Extract the requested "
            "structured data from the given text.\n\n"
            f"Target schema: {self.schema.__name__}\n"
            f"Fields:\n{field_desc}\n\n"
            "Respond with ONLY a valid JSON object matching this schema. "
            "Do not include markdown code fences, explanations, or any text "
            "outside the JSON object.\n\n"
            f"JSON Schema:\n{json_schema}"
        )

        logger.debug(
            "DataExtractorSkill initialised: schema=%s, model=%s",
            self.schema.__name__,
            self.model,
        )

    def __repr__(self) -> str:
        schema_name = self.schema.__name__ if self.schema else "None"
        return (
            f"DataExtractorSkill(name={self.name!r}, "
            f"schema={schema_name}, model={self.model!r})"
        )


__all__ = ["DataExtractorSkill"]

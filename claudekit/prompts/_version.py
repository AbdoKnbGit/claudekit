"""Prompt version data model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class PromptVersion:
    """A single version of a named prompt.

    Parameters
    ----------
    name:
        The prompt family name.
    version:
        Version identifier (e.g. ``"1.0"``, ``"2.1-beta"``).
    system:
        The system prompt text.
    user_template:
        Optional user message template with ``{variable}`` placeholders.
    created_at:
        Timestamp when this version was created.
    metadata:
        Arbitrary key/value pairs (author, notes, etc.).

    Example
    -------
    >>> pv = PromptVersion(name="support", version="1.0", system="Be helpful.")
    """

    name: str
    version: str
    system: str
    user_template: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def render(self, **variables: str) -> str:
        """Render the user template with the given variables.

        Args:
            **variables: Template variable values.

        Returns:
            The rendered user message string.
        """
        if not self.user_template:
            return ""
        return self.user_template.format(**variables)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "system": self.system,
            "user_template": self.user_template,
            "created_at": self.created_at.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PromptVersion:
        """Deserialize from a dictionary."""
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now()
        return cls(
            name=data["name"],
            version=data["version"],
            system=data["system"],
            user_template=data.get("user_template", ""),
            created_at=created_at,
            metadata=data.get("metadata", {}),
        )


__all__ = ["PromptVersion"]

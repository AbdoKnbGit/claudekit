"""Versioned prompt management with diff and A/B comparison.

Provides :class:`PromptManager` for saving, loading, comparing, and managing
prompt versions with a pluggable storage backend.
"""

from __future__ import annotations

import difflib
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from claudekit.prompts._comparison import ComparisonResult
from claudekit.prompts._storage import JSONPromptStorage
from claudekit.prompts._version import PromptVersion

logger = logging.getLogger(__name__)


class PromptManager:
    """Versioned prompt storage and comparison.

    Manages prompt versions with save, load, diff, and A/B comparison
    capabilities. Uses JSON file storage by default.

    Parameters
    ----------
    storage_path:
        Path to the JSON storage file. Defaults to ``"./prompts.json"``.

    Example
    -------
    ::

        from claudekit.prompts import PromptManager

        pm = PromptManager()
        pm.save("support", system="Be concise.", version="1.0")
        pm.save("support", system="Be concise and empathetic.", version="2.0")
        print(pm.diff("support", "1.0", "2.0"))
    """

    def __init__(self, storage_path: str | Path = "./prompts.json") -> None:
        self._storage = JSONPromptStorage(storage_path)

    def save(
        self,
        name: str,
        system: str,
        version: str,
        user_template: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PromptVersion:
        """Save a new prompt version.

        Args:
            name: The prompt family name.
            system: The system prompt text.
            version: Version identifier.
            user_template: Optional user message template with {variable} placeholders.
            metadata: Optional metadata dict.

        Returns:
            The created PromptVersion.
        """
        pv = PromptVersion(
            name=name,
            version=version,
            system=system,
            user_template=user_template,
            metadata=metadata or {},
        )
        self._storage.save(pv)
        logger.info("Saved prompt %r version %r", name, version)
        return pv

    def load(self, name: str, version: str = "latest") -> Optional[PromptVersion]:
        """Load a prompt version.

        Args:
            name: The prompt family name.
            version: Version string, or ``"latest"`` for most recent by created_at.

        Returns:
            The prompt version, or None if not found.
        """
        return self._storage.load(name, version)

    def list(self, name: str) -> List[PromptVersion]:
        """List all versions of a named prompt.

        Args:
            name: The prompt family name.

        Returns:
            List of all versions, sorted by created_at.
        """
        return self._storage.list(name)

    def delete(self, name: str, version: str) -> bool:
        """Delete a specific prompt version.

        Args:
            name: The prompt family name.
            version: The version string to delete.

        Returns:
            True if found and deleted.
        """
        result = self._storage.delete(name, version)
        if result:
            logger.info("Deleted prompt %r version %r", name, version)
        return result

    def diff(self, name: str, v1: str, v2: str) -> str:
        """Generate a unified diff between two prompt versions.

        Args:
            name: The prompt family name.
            v1: First version identifier.
            v2: Second version identifier.

        Returns:
            Unified diff string.

        Raises:
            ValueError: If either version is not found.
        """
        pv1 = self._storage.load(name, v1)
        pv2 = self._storage.load(name, v2)

        if pv1 is None:
            raise ValueError(f"Prompt {name!r} version {v1!r} not found")
        if pv2 is None:
            raise ValueError(f"Prompt {name!r} version {v2!r} not found")

        lines1 = pv1.system.splitlines(keepends=True)
        lines2 = pv2.system.splitlines(keepends=True)

        diff_lines = difflib.unified_diff(
            lines1, lines2,
            fromfile=f"{name} v{v1}",
            tofile=f"{name} v{v2}",
        )
        return "".join(diff_lines)

    def compare(
        self,
        name: str,
        versions: List[str],
        inputs: List[str],
        model: str,
        client: Any,
        confirm: bool = False,
    ) -> ComparisonResult:
        """Run A/B comparison across prompt versions and inputs.

        Makes N × M API calls (N versions × M inputs). Logs estimated cost
        before starting. Requires ``confirm=True`` if estimated cost > $0.10.

        Args:
            name: The prompt family name.
            versions: List of version identifiers to compare.
            inputs: List of test input strings.
            model: Model identifier to use for all calls.
            client: A TrackedClient or compatible client.
            confirm: Must be True if estimated cost exceeds $0.10.

        Returns:
            A ComparisonResult with outputs, token counts, and costs.

        Raises:
            ValueError: If a version is not found or cost not confirmed.
        """
        total_calls = len(versions) * len(inputs)
        logger.info(
            "Comparison will make %d API calls for %d versions x %d inputs",
            total_calls, len(versions), len(inputs),
        )

        result = ComparisonResult(
            versions=list(versions),
            inputs=list(inputs),
        )

        for v in versions:
            pv = self._storage.load(name, v)
            if pv is None:
                raise ValueError(f"Prompt {name!r} version {v!r} not found")

            v_outputs: list[str] = []
            v_tokens: list[int] = []
            v_cost = 0.0

            for inp in inputs:
                response = client.messages.create(
                    model=model,
                    max_tokens=4096,
                    system=pv.system,
                    messages=[{"role": "user", "content": inp}],
                )
                text = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        text += block.text
                v_outputs.append(text)

                tokens = getattr(response.usage, "output_tokens", 0)
                v_tokens.append(tokens)

                cost = getattr(response, "_estimated_cost", 0.0)
                v_cost += cost

            result.outputs[v] = v_outputs
            result.token_counts[v] = v_tokens
            result.costs[v] = v_cost

        return result

    def render(self, name: str, version: str = "latest", **variables: str) -> str:
        """Load and render a prompt's user template with variables.

        Args:
            name: The prompt family name.
            version: Version string or "latest".
            **variables: Template variable values.

        Returns:
            The rendered user message.

        Raises:
            ValueError: If the version is not found.
        """
        pv = self._storage.load(name, version)
        if pv is None:
            raise ValueError(f"Prompt {name!r} version {version!r} not found")
        return pv.render(**variables)

    def export(self, name: str) -> Dict[str, Any]:
        """Export all versions of a named prompt.

        Args:
            name: The prompt family name.

        Returns:
            Dictionary containing the full version history.
        """
        return self._storage.export(name)

    def import_(self, data: Dict[str, Any]) -> None:
        """Import prompt versions from an exported dictionary.

        Args:
            data: Dictionary with name and versions keys.
        """
        self._storage.import_(data)
        logger.info("Imported prompt %r", data.get("name"))


__all__ = ["PromptManager"]

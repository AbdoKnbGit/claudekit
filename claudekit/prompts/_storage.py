"""JSON file storage backend for prompt versions."""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from claudekit.prompts._version import PromptVersion

logger = logging.getLogger(__name__)


class JSONPromptStorage:
    """Stores prompt versions in a JSON file.

    Uses atomic writes (write to temp file then rename) to prevent
    corruption from concurrent writes.

    Parameters
    ----------
    path:
        File path for the JSON storage file. Created if it does not exist.

    Example
    -------
    >>> storage = JSONPromptStorage("./prompts.json")
    >>> storage.save(pv)
    """

    def __init__(self, path: str | Path = "./prompts.json") -> None:
        self._path = Path(path)
        self._data: Dict[str, List[Dict[str, Any]]] = {}
        self._load()

    def _load(self) -> None:
        """Load data from the JSON file, or init empty if not found."""
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                logger.debug("Loaded prompt storage from %s", self._path)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to load prompt storage: %s", exc)
                self._data = {}
        else:
            self._data = {}

    def _save(self) -> None:
        """Atomically write data to the JSON file."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Write to temp file then rename for atomicity
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self._path.parent), suffix=".tmp"
        )
        try:
            with open(fd, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, default=str)
            Path(tmp_path).replace(self._path)
            logger.debug("Saved prompt storage to %s", self._path)
        except OSError:
            Path(tmp_path).unlink(missing_ok=True)
            raise

    def save(self, version: PromptVersion) -> None:
        """Save a prompt version to storage.

        Args:
            version: The prompt version to save.
        """
        name = version.name
        if name not in self._data:
            self._data[name] = []
        self._data[name].append(version.to_dict())
        self._save()

    def load(self, name: str, version: str = "latest") -> Optional[PromptVersion]:
        """Load a prompt version by name and version.

        Args:
            name: The prompt family name.
            version: Version string, or ``"latest"`` for the most recent.

        Returns:
            The prompt version, or ``None`` if not found.
        """
        versions = self._data.get(name, [])
        if not versions:
            return None

        if version == "latest":
            # Sort by created_at timestamp, return most recent
            sorted_versions = sorted(
                versions,
                key=lambda v: v.get("created_at", ""),
                reverse=True,
            )
            return PromptVersion.from_dict(sorted_versions[0])

        for v in versions:
            if v.get("version") == version:
                return PromptVersion.from_dict(v)
        return None

    def list(self, name: str) -> List[PromptVersion]:
        """List all versions of a named prompt.

        Args:
            name: The prompt family name.

        Returns:
            List of all versions, sorted by created_at.
        """
        versions = self._data.get(name, [])
        result = [PromptVersion.from_dict(v) for v in versions]
        result.sort(key=lambda pv: pv.created_at)
        return result

    def delete(self, name: str, version: str) -> bool:
        """Delete a specific prompt version.

        Args:
            name: The prompt family name.
            version: The version string to delete.

        Returns:
            ``True`` if the version was found and deleted.
        """
        versions = self._data.get(name, [])
        for i, v in enumerate(versions):
            if v.get("version") == version:
                versions.pop(i)
                self._save()
                return True
        return False

    def export(self, name: str) -> Dict[str, Any]:
        """Export all versions of a named prompt.

        Args:
            name: The prompt family name.

        Returns:
            Dictionary containing the full version history.
        """
        return {"name": name, "versions": list(self._data.get(name, []))}

    def import_(self, data: Dict[str, Any]) -> None:
        """Import prompt versions from an exported dictionary.

        Args:
            data: Dictionary with ``name`` and ``versions`` keys.
        """
        name = data["name"]
        self._data[name] = data.get("versions", [])
        self._save()


__all__ = ["JSONPromptStorage"]

"""Prebuilt file-system tools.

Provides tools for reading, writing, listing, and checking the existence of
files. All paths are resolved relative to the current working directory
unless absolute.

Example::

    from claudekit.tools.prebuilt import read_file, write_file, list_dir

    content = read_file("config.yaml")
    write_file("output.txt", "Hello, world!")
    entries = list_dir(".", pattern="*.py")
"""

from __future__ import annotations

import logging
from pathlib import Path

from claudekit.tools._decorator import tool

logger = logging.getLogger(__name__)


@tool
def read_file(path: str, encoding: str = "utf-8") -> str:
    """Read the contents of a file.

    Args:
        path: Path to the file to read. Can be absolute or relative to the
            current working directory.
        encoding: Character encoding to use. Defaults to ``utf-8``.

    Returns:
        The file contents as a string.
    """
    resolved = Path(path).resolve()
    logger.debug("Reading file: %s", resolved)

    try:
        return resolved.read_text(encoding=encoding)
    except FileNotFoundError:
        return f"Error: File not found: {resolved}"
    except PermissionError:
        return f"Error: Permission denied: {resolved}"
    except UnicodeDecodeError as exc:
        return f"Error: Could not decode file with encoding {encoding!r}: {exc}"
    except Exception as exc:
        return f"Error reading file {resolved}: {type(exc).__name__}: {exc}"


@tool
def write_file(path: str, content: str, append: bool = False) -> str:
    """Write content to a file.

    Creates parent directories automatically if they do not exist.

    Args:
        path: Path to the file to write. Can be absolute or relative.
        content: The text content to write.
        append: If True, append to the file instead of overwriting.
            Defaults to False.

    Returns:
        A confirmation message indicating success or an error description.
    """
    resolved = Path(path).resolve()
    logger.debug("Writing file: %s (append=%s)", resolved, append)

    try:
        # Ensure parent directory exists
        resolved.parent.mkdir(parents=True, exist_ok=True)

        mode = "a" if append else "w"
        with resolved.open(mode, encoding="utf-8") as f:
            f.write(content)

        action = "Appended to" if append else "Wrote"
        return f"{action} {resolved} ({len(content)} characters)"

    except PermissionError:
        return f"Error: Permission denied: {resolved}"
    except Exception as exc:
        return f"Error writing file {resolved}: {type(exc).__name__}: {exc}"


@tool
def list_dir(path: str = ".", pattern: str = "*") -> list[str]:
    """List files and directories matching a glob pattern.

    Args:
        path: Directory path to list. Defaults to the current directory.
        pattern: Glob pattern to filter entries. Defaults to ``*`` (all).

    Returns:
        A sorted list of matching file/directory names relative to the
        given path.
    """
    resolved = Path(path).resolve()
    logger.debug("Listing directory: %s with pattern %r", resolved, pattern)

    try:
        if not resolved.is_dir():
            return [f"Error: Not a directory: {resolved}"]

        entries = sorted(str(p.relative_to(resolved)) for p in resolved.glob(pattern))
        return entries

    except PermissionError:
        return [f"Error: Permission denied: {resolved}"]
    except Exception as exc:
        return [f"Error listing {resolved}: {type(exc).__name__}: {exc}"]


@tool
def file_exists(path: str) -> bool:
    """Check whether a file exists at the given path.

    Args:
        path: The file path to check.

    Returns:
        True if the file exists, False otherwise.
    """
    resolved = Path(path).resolve()
    return resolved.exists()

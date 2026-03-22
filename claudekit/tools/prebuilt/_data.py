"""Prebuilt data-processing tools.

Provides tools for parsing JSON, parsing CSV, and formatting tabular data
for display. Uses only the Python standard library.

Example::

    from claudekit.tools.prebuilt import parse_json, parse_csv, format_table

    data = parse_json('{"name": "Alice", "age": 30}')
    rows = parse_csv("name,age\\nAlice,30\\nBob,25")
    table = format_table(rows)
"""

from __future__ import annotations

import csv
import io
import json
import logging
from typing import Any

from claudekit.tools._decorator import tool

logger = logging.getLogger(__name__)


@tool
def parse_json(text: str) -> dict[str, Any] | list[Any]:
    """Parse a JSON string into a Python object.

    Args:
        text: A valid JSON string.

    Returns:
        The parsed Python object (dict or list).
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning("JSON parse error: %s", exc)
        return {"error": f"Invalid JSON: {exc}"}


@tool
def parse_csv(text: str, delimiter: str = ",") -> list[dict[str, str]]:
    """Parse CSV text into a list of dictionaries.

    The first row is treated as the header row. Each subsequent row becomes
    a dictionary mapping column names to values.

    Args:
        text: CSV-formatted text.
        delimiter: Field delimiter character. Defaults to ``","`` (comma).

    Returns:
        A list of dictionaries, one per data row.
    """
    try:
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        rows = list(reader)
        logger.debug("Parsed %d CSV rows.", len(rows))
        return rows
    except Exception as exc:
        logger.warning("CSV parse error: %s", exc)
        return [{"error": f"Failed to parse CSV: {type(exc).__name__}: {exc}"}]


@tool
def format_table(data: list[dict[str, str]], max_rows: int = 50) -> str:
    """Format a list of dictionaries as a plain-text table.

    Produces a simple aligned text table suitable for display to an LLM
    or in a terminal.

    Args:
        data: List of row dictionaries. All dicts should share the same keys.
        max_rows: Maximum number of data rows to display. Defaults to 50.

    Returns:
        A formatted plain-text table string.
    """
    if not data:
        return "(empty table)"

    # Collect all unique column names preserving insertion order
    columns: list[str] = []
    for row in data:
        for key in row:
            if key not in columns:
                columns.append(key)

    if not columns:
        return "(no columns)"

    # Determine column widths
    col_widths: dict[str, int] = {}
    for col in columns:
        col_widths[col] = len(col)

    display_data = data[:max_rows]
    for row in display_data:
        for col in columns:
            value = str(row.get(col, ""))
            col_widths[col] = max(col_widths[col], len(value))

    # Build the table
    lines: list[str] = []

    # Header
    header_parts = [col.ljust(col_widths[col]) for col in columns]
    header_line = " | ".join(header_parts)
    lines.append(header_line)

    # Separator
    sep_parts = ["-" * col_widths[col] for col in columns]
    lines.append("-+-".join(sep_parts))

    # Data rows
    for row in display_data:
        row_parts = [str(row.get(col, "")).ljust(col_widths[col]) for col in columns]
        lines.append(" | ".join(row_parts))

    # Truncation notice
    if len(data) > max_rows:
        lines.append(f"... ({len(data) - max_rows} more rows not shown)")

    return "\n".join(lines)

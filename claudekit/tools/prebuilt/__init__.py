"""Prebuilt tools for common tasks.

Re-exports every prebuilt tool so that callers can import from a single
location::

    from claudekit.tools.prebuilt import read_file, run_python, web_search
"""

from __future__ import annotations

from claudekit.tools.prebuilt._code import run_bash, run_python
from claudekit.tools.prebuilt._data import format_table, parse_csv, parse_json
from claudekit.tools.prebuilt._files import file_exists, list_dir, read_file, write_file
from claudekit.tools.prebuilt._web import web_fetch, web_search

__all__ = [
    # Code execution
    "run_bash",
    "run_python",
    # Data processing
    "format_table",
    "parse_csv",
    "parse_json",
    # File system
    "file_exists",
    "list_dir",
    "read_file",
    "write_file",
    # Web
    "web_fetch",
    "web_search",
]

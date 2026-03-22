"""Prebuilt code execution tools.

Provides tools for running Python code and shell commands in isolated
subprocesses with configurable timeouts. Code is **never** executed in
the main process.

Example::

    from claudekit.tools.prebuilt import run_python, run_bash

    result = run_python("print(2 + 2)")
    # {"stdout": "4\\n", "stderr": "", "exit_code": 0}

    result = run_bash("ls -la", timeout_seconds=5)
    # {"stdout": "...", "stderr": "", "exit_code": 0}
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from claudekit.tools._decorator import tool

logger = logging.getLogger(__name__)


@tool
def run_python(code: str, timeout_seconds: int = 10) -> dict[str, str | int]:
    """Execute Python code in a subprocess and return the result.

    The code is passed to a fresh Python interpreter via ``-c``. It runs in
    complete isolation from the main process.

    Args:
        code: Python source code to execute.
        timeout_seconds: Maximum execution time in seconds. Defaults to 10.

    Returns:
        A dictionary with ``stdout``, ``stderr``, and ``exit_code`` keys.
    """
    logger.debug(
        "Running Python code (timeout=%ds, %d chars).",
        timeout_seconds,
        len(code),
    )

    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": f"Execution timed out after {timeout_seconds} seconds.",
            "exit_code": -1,
        }
    except Exception as exc:
        return {
            "stdout": "",
            "stderr": f"Failed to execute Python code: {type(exc).__name__}: {exc}",
            "exit_code": -1,
        }


@tool
def run_bash(
    command: str,
    timeout_seconds: int = 10,
    working_dir: str = ".",
) -> dict[str, str | int]:
    """Execute a shell command in a subprocess and return the result.

    The command is executed via the system shell (``/bin/sh -c`` on Unix,
    ``cmd /c`` on Windows). It runs in complete isolation from the main
    process.

    Args:
        command: The shell command to execute.
        timeout_seconds: Maximum execution time in seconds. Defaults to 10.
        working_dir: Working directory for the command. Defaults to ``"."``.

    Returns:
        A dictionary with ``stdout``, ``stderr``, and ``exit_code`` keys.
    """
    resolved_cwd = Path(working_dir).resolve()
    logger.debug(
        "Running bash command (timeout=%ds, cwd=%s): %s",
        timeout_seconds,
        resolved_cwd,
        command[:200],
    )

    if not resolved_cwd.is_dir():
        return {
            "stdout": "",
            "stderr": f"Working directory does not exist: {resolved_cwd}",
            "exit_code": -1,
        }

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=str(resolved_cwd),
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": f"Execution timed out after {timeout_seconds} seconds.",
            "exit_code": -1,
        }
    except Exception as exc:
        return {
            "stdout": "",
            "stderr": f"Failed to execute command: {type(exc).__name__}: {exc}",
            "exit_code": -1,
        }

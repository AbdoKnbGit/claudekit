"""Assertion builders for validating Claude API responses.

Provides the ``expect`` namespace with composable assertion objects.
Used with :func:`~claudekit.testing.assert_response`::

    from claudekit.testing import assert_response, expect

    assert_response(response,
        expect.contains("Paris"),
        expect.max_tokens(100),
        expect.stop_reason("end_turn"),
    )
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable


class Assertion:
    """A single response assertion with rich failure diagnostics.

    Args:
        name: Display name like ``expect.contains("Paris")``.
        description: Human-readable description of what is checked.
        check: A callable ``(response) -> bool``.
        format_actual: A callable ``(response) -> str`` for failure messages.
    """

    def __init__(
        self,
        name: str,
        description: str,
        check: Callable[[Any], bool],
        format_actual: Callable[[Any], str] | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self._check = check
        self._format_actual = format_actual or (lambda r: repr(r))

    def evaluate(self, response: Any) -> tuple[bool, str]:
        """Evaluate this assertion against a response.

        Returns:
            A tuple of ``(passed, message)``.
        """
        try:
            passed = self._check(response)
        except Exception as exc:
            return False, f"raised {type(exc).__name__}: {exc}"
        if passed:
            return True, "OK"
        actual = self._format_actual(response)
        return False, (
            f"{self.name} FAILED\n"
            f"  Expected : {self.description}\n"
            f"  Actual   : {actual}"
        )


def _get_text(response: Any) -> str:
    """Extract text from a response."""
    for block in getattr(response, "content", []):
        if getattr(block, "type", "") == "text":
            return getattr(block, "text", "")
    return ""


def _get_output_tokens(response: Any) -> int:
    usage = getattr(response, "usage", None)
    return getattr(usage, "output_tokens", 0) if usage else 0


def _get_tool_uses(response: Any) -> list[Any]:
    return [b for b in getattr(response, "content", []) if getattr(b, "type", "") == "tool_use"]


# ── Assertion builders ───────────────────────────────────────────────────── #


def contains(text: str) -> Assertion:
    """Response text includes *text* as a substring."""
    return Assertion(
        name=f'expect.contains({text!r})',
        description=f"response text contains {text!r}",
        check=lambda r: text in _get_text(r),
        format_actual=lambda r: f"text = {_get_text(r)!r}",
    )


def not_contains(text: str) -> Assertion:
    """Response text does NOT include *text*."""
    return Assertion(
        name=f'expect.not_contains({text!r})',
        description=f"response text does not contain {text!r}",
        check=lambda r: text not in _get_text(r),
        format_actual=lambda r: f"text = {_get_text(r)!r}",
    )


def equals(text: str) -> Assertion:
    """Response text is exactly *text*."""
    return Assertion(
        name=f'expect.equals({text!r})',
        description=f"response text equals {text!r}",
        check=lambda r: _get_text(r) == text,
        format_actual=lambda r: f"text = {_get_text(r)!r}",
    )


def matches(pattern: str) -> Assertion:
    """Response text matches regex *pattern*."""
    return Assertion(
        name=f'expect.matches({pattern!r})',
        description=f"response text matches /{pattern}/",
        check=lambda r: bool(re.search(pattern, _get_text(r))),
        format_actual=lambda r: f"text = {_get_text(r)!r}",
    )


def max_tokens(n: int) -> Assertion:
    """Output token count ≤ *n*."""
    return Assertion(
        name=f'expect.max_tokens({n})',
        description=f"output_tokens <= {n}",
        check=lambda r: _get_output_tokens(r) <= n,
        format_actual=lambda r: f"output_tokens = {_get_output_tokens(r)}",
    )


def min_tokens(n: int) -> Assertion:
    """Output token count ≥ *n*."""
    return Assertion(
        name=f'expect.min_tokens({n})',
        description=f"output_tokens >= {n}",
        check=lambda r: _get_output_tokens(r) >= n,
        format_actual=lambda r: f"output_tokens = {_get_output_tokens(r)}",
    )


def stop_reason(reason: str) -> Assertion:
    """``stop_reason`` equals *reason*."""
    return Assertion(
        name=f'expect.stop_reason({reason!r})',
        description=f"stop_reason == {reason!r}",
        check=lambda r: getattr(r, "stop_reason", None) == reason,
        format_actual=lambda r: f"stop_reason = {getattr(r, 'stop_reason', None)!r}",
    )


def tool_called(name: str) -> Assertion:
    """At least one ``tool_use`` block with the given *name*."""
    return Assertion(
        name=f'expect.tool_called({name!r})',
        description=f"tool_use block with name={name!r} present",
        check=lambda r: any(getattr(b, "name", "") == name for b in _get_tool_uses(r)),
        format_actual=lambda r: f"tool_use names = {[getattr(b, 'name', '') for b in _get_tool_uses(r)]}",
    )


def tool_called_with(name: str, **kwargs: Any) -> Assertion:
    """A ``tool_use`` block with *name* and matching input fields."""
    return Assertion(
        name=f'expect.tool_called_with({name!r}, {kwargs})',
        description=f"tool_use {name!r} called with {kwargs}",
        check=lambda r: any(
            getattr(b, "name", "") == name and
            all(getattr(b, "input", {}).get(k) == v for k, v in kwargs.items())
            for b in _get_tool_uses(r)
        ),
        format_actual=lambda r: f"tool_use blocks = {[(getattr(b, 'name', ''), getattr(b, 'input', {})) for b in _get_tool_uses(r)]}",
    )


def no_tool_call() -> Assertion:
    """No ``tool_use`` blocks in the response."""
    return Assertion(
        name='expect.no_tool_call()',
        description="no tool_use blocks",
        check=lambda r: len(_get_tool_uses(r)) == 0,
        format_actual=lambda r: f"tool_use count = {len(_get_tool_uses(r))}",
    )


def tool_count(n: int) -> Assertion:
    """Exactly *n* ``tool_use`` blocks."""
    return Assertion(
        name=f'expect.tool_count({n})',
        description=f"exactly {n} tool_use blocks",
        check=lambda r: len(_get_tool_uses(r)) == n,
        format_actual=lambda r: f"tool_use count = {len(_get_tool_uses(r))}",
    )


def json_valid() -> Assertion:
    """Response text is valid JSON."""
    def _check(r: Any) -> bool:
        try:
            json.loads(_get_text(r))
            return True
        except (json.JSONDecodeError, ValueError):
            return False

    return Assertion(
        name='expect.json_valid()',
        description="response text is valid JSON",
        check=_check,
        format_actual=lambda r: f"text = {_get_text(r)[:200]!r}",
    )


def json_contains(key: str, value: Any = ...) -> Assertion:
    """Parsed JSON has *key*, optionally with *value*."""
    def _check(r: Any) -> bool:
        try:
            data = json.loads(_get_text(r))
        except (json.JSONDecodeError, ValueError):
            return False
        if key not in data:
            return False
        if value is not ...:
            return data[key] == value
        return True

    desc = f"JSON contains key {key!r}" + (f" = {value!r}" if value is not ... else "")
    return Assertion(
        name=f'expect.json_contains({key!r}{", " + repr(value) if value is not ... else ""})',
        description=desc,
        check=_check,
        format_actual=lambda r: f"text = {_get_text(r)[:200]!r}",
    )


def model_used(model: str) -> Assertion:
    """``response.model`` matches *model*."""
    return Assertion(
        name=f'expect.model_used({model!r})',
        description=f"response.model == {model!r}",
        check=lambda r: getattr(r, "model", "") == model,
        format_actual=lambda r: f"model = {getattr(r, 'model', '')!r}",
    )


def has_text() -> Assertion:
    """At least one text content block with non-empty text."""
    return Assertion(
        name='expect.has_text()',
        description="at least one text block with content",
        check=lambda r: bool(_get_text(r)),
        format_actual=lambda r: f"text blocks = {[getattr(b, 'text', '') for b in getattr(r, 'content', []) if getattr(b, 'type', '') == 'text']}",
    )


def custom(fn: Callable[[Any], bool], name: str = "custom") -> Assertion:
    """Custom assertion using *fn*."""
    return Assertion(
        name=f'expect.custom({name})',
        description=f"custom assertion: {name}",
        check=fn,
        format_actual=lambda r: f"model={getattr(r, 'model', '?')}, text={_get_text(r)[:100]!r}",
    )


__all__ = [
    "Assertion",
    "contains",
    "not_contains",
    "equals",
    "matches",
    "max_tokens",
    "min_tokens",
    "stop_reason",
    "tool_called",
    "tool_called_with",
    "no_tool_call",
    "tool_count",
    "json_valid",
    "json_contains",
    "model_used",
    "has_text",
    "custom",
]

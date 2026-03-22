"""Batch assertion evaluation for API responses.

Evaluates a list of :class:`~claudekit.testing._expect.Assertion` objects
against a response and reports all failures in a single ``AssertionError``::

    from claudekit.testing import assert_response, expect

    assert_response(response,
        expect.contains("Paris"),
        expect.stop_reason("end_turn"),
        expect.max_tokens(100),
    )
"""

from __future__ import annotations

from typing import Any

from claudekit.testing._expect import Assertion


def assert_response(response: Any, *assertions: Assertion) -> None:
    """Evaluate all assertions against *response*.

    Runs every assertion (does not short-circuit) and raises a single
    ``AssertionError`` listing all failures.

    Args:
        response: An ``anthropic.types.Message`` or compatible object.
        *assertions: :class:`Assertion` objects from the ``expect`` namespace.

    Raises:
        AssertionError: If one or more assertions fail, with a formatted
            message listing each failure and its diagnostics.

    Example::

        assert_response(response,
            expect.contains("Paris"),
            expect.stop_reason("end_turn"),
        )
    """
    if not assertions:
        return

    failures: list[str] = []
    for assertion in assertions:
        passed, message = assertion.evaluate(response)
        if not passed:
            failures.append(message)

    if failures:
        model = getattr(response, "model", "unknown")
        header = f"Response assertion(s) failed (model={model}):"
        detail = "\n\n".join(failures)
        raise AssertionError(f"{header}\n\n{detail}")


def assert_agent_result(result: Any, *assertions: Assertion) -> None:
    """Evaluate assertions against an agent result.

    Works with any object that has a ``.response`` or ``.message`` attribute,
    or is itself a response-like object.

    Args:
        result: An agent result or response object.
        *assertions: :class:`Assertion` objects.

    Raises:
        AssertionError: If one or more assertions fail.
    """
    response = result
    if hasattr(result, "response"):
        response = result.response
    elif hasattr(result, "message"):
        response = result.message
    assert_response(response, *assertions)


__all__ = ["assert_response", "assert_agent_result"]

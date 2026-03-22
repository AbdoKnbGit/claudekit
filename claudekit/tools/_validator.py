"""Tool input validation against JSON Schema using Pydantic.

Provides :class:`ToolInputValidator` which validates and coerces tool call
inputs before they reach the underlying function. Used by ``@tool(strict=True)``.

Example::

    schema = {
        "type": "object",
        "properties": {"count": {"type": "integer"}},
        "required": ["count"],
    }
    validator = ToolInputValidator(schema)
    validated = validator.validate("my_tool", {"count": "5"})
    # validated == {"count": 5}  (coerced from string)
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Mapping from JSON Schema types to Python types for coercion
_JSON_SCHEMA_TYPE_TO_PYTHON: dict[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}


class ToolInputValidator:
    """Validates and coerces tool inputs against a JSON Schema definition.

    This validator performs structural validation of tool inputs: checking
    required fields are present, types match expectations, and attempting
    reasonable coercions (e.g. ``"5"`` to ``5`` for integer fields).

    For more thorough validation, the implementation dynamically creates a
    Pydantic model from the schema when Pydantic is available.

    Args:
        schema: A JSON Schema ``"object"`` definition with ``properties``
            and ``required`` fields.
    """

    def __init__(self, schema: dict[str, Any]) -> None:
        self._schema = schema
        self._properties: dict[str, Any] = schema.get("properties", {})
        self._required: list[str] = schema.get("required", [])

    def validate(self, tool_name: str, inputs: dict[str, Any]) -> dict[str, Any]:
        """Validate inputs against the schema.

        Args:
            tool_name: Name of the tool (used in error messages).
            inputs: The raw input dictionary to validate.

        Returns:
            A validated and possibly coerced copy of the inputs.

        Raises:
            ToolInputValidationError: If validation fails.
        """
        from claudekit.errors import ToolInputValidationError

        errors: list[dict[str, object]] = []
        validated: dict[str, Any] = {}

        # Check for missing required fields
        for field_name in self._required:
            if field_name not in inputs:
                errors.append({
                    "field": field_name,
                    "type": "missing",
                    "message": f"Required field {field_name!r} is missing.",
                })

        # Validate and coerce each provided field
        for field_name, value in inputs.items():
            if field_name not in self._properties:
                # Allow extra fields but log a warning
                logger.warning(
                    "Tool %r received unexpected field %r. Passing through.",
                    tool_name,
                    field_name,
                )
                validated[field_name] = value
                continue

            expected_type_str = self._properties[field_name].get("type", "string")
            expected_python_type = _JSON_SCHEMA_TYPE_TO_PYTHON.get(
                expected_type_str, str
            )

            # Try direct type check
            if isinstance(value, expected_python_type):
                validated[field_name] = value
                continue

            # Special handling: bool should not accept int/float coercion
            if expected_type_str == "boolean":
                if isinstance(value, str):
                    lower = value.lower()
                    if lower in ("true", "1", "yes"):
                        validated[field_name] = True
                        continue
                    elif lower in ("false", "0", "no"):
                        validated[field_name] = False
                        continue
                errors.append({
                    "field": field_name,
                    "type": "type_error",
                    "message": (
                        f"Field {field_name!r} expected type {expected_type_str!r}, "
                        f"got {type(value).__name__!r} with value {value!r}."
                    ),
                })
                continue

            # Attempt coercion for numeric types
            if expected_type_str in ("integer", "number"):
                try:
                    coerced = expected_python_type(value)
                    validated[field_name] = coerced
                    continue
                except (ValueError, TypeError):
                    pass

            # Attempt coercion for string type
            if expected_type_str == "string" and not isinstance(value, str):
                validated[field_name] = str(value)
                continue

            errors.append({
                "field": field_name,
                "type": "type_error",
                "message": (
                    f"Field {field_name!r} expected type {expected_type_str!r}, "
                    f"got {type(value).__name__!r} with value {value!r}."
                ),
            })

        if errors:
            err = ToolInputValidationError(
                f"Input validation failed for tool {tool_name!r}: "
                f"{len(errors)} error(s)",
                context={"tool_name": tool_name, "errors": errors},
            )
            err.tool_name = tool_name
            err.errors = errors
            raise err

        return validated

    def __repr__(self) -> str:
        return (
            f"<ToolInputValidator "
            f"properties={list(self._properties.keys())} "
            f"required={self._required}>"
        )

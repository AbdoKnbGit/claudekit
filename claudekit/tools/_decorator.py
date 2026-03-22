"""The ``@tool`` decorator for turning Python functions into Anthropic tool definitions.

Inspects function signatures and Google-style docstrings to automatically
generate the JSON schema that the Anthropic API expects for tool definitions.

Example::

    from claudekit.tools import tool

    @tool
    def get_weather(city: str, units: str = "celsius") -> str:
        \"\"\"Get current weather for a city.

        Args:
            city: The city to look up weather for.
            units: Temperature units, either 'celsius' or 'fahrenheit'.

        Returns:
            A string describing the current weather.
        \"\"\"
        ...
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import logging
import re
import textwrap
from typing import Any, Callable, TypeVar, overload

logger = logging.getLogger(__name__)

_RESULT_WARNING_THRESHOLD = 100_000

# Mapping from Python type annotations to JSON Schema types.
_TYPE_MAP: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def _python_type_to_json_schema(annotation: Any) -> str:
    """Convert a Python type annotation to a JSON Schema type string.

    Args:
        annotation: The Python type annotation to convert.

    Returns:
        The corresponding JSON Schema type string. Defaults to ``"string"``
        for unrecognised annotations.
    """
    # Handle typing generics (e.g. list[str] -> "array")
    origin = getattr(annotation, "__origin__", None)
    if origin is not None:
        return _TYPE_MAP.get(origin, "string")
    return _TYPE_MAP.get(annotation, "string")


def _parse_google_docstring_args(docstring: str | None) -> dict[str, str]:
    """Parse the ``Args:`` section of a Google-style docstring.

    Args:
        docstring: The raw docstring text. May be ``None``.

    Returns:
        A mapping from parameter name to its description.
    """
    if not docstring:
        return {}

    docstring = textwrap.dedent(docstring)
    descriptions: dict[str, str] = {}

    # Find the Args: section
    args_match = re.search(r"^Args:\s*$", docstring, re.MULTILINE)
    if not args_match:
        return descriptions

    # Extract lines after "Args:" until the next section header or end of string
    remaining = docstring[args_match.end() :]
    # A section header is a line that starts at column 0 with a word followed by colon
    section_end = re.search(r"^\S", remaining, re.MULTILINE)
    if section_end:
        remaining = remaining[: section_end.start()]

    # Parse individual argument entries
    # Pattern: leading whitespace, param_name: description (possibly multi-line)
    current_param: str | None = None
    current_desc_lines: list[str] = []

    for line in remaining.splitlines():
        # Check if this is a new parameter line
        param_match = re.match(r"^\s+(\w+)\s*(?:\([^)]*\))?\s*:\s*(.*)", line)
        if param_match:
            # Save previous parameter
            if current_param is not None:
                descriptions[current_param] = " ".join(current_desc_lines).strip()
            current_param = param_match.group(1)
            current_desc_lines = [param_match.group(2).strip()]
        elif current_param is not None and line.strip():
            # Continuation line for current parameter
            current_desc_lines.append(line.strip())

    # Save last parameter
    if current_param is not None:
        descriptions[current_param] = " ".join(current_desc_lines).strip()

    return descriptions


def _build_tool_definition(
    func: Callable[..., Any],
    name: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """Build an Anthropic tool definition dict from a callable.

    Args:
        func: The function to generate a tool definition for.
        name: Override for the tool name. Defaults to ``func.__name__``.
        description: Override for the tool description. Defaults to the first
            line of the docstring.

    Returns:
        A dictionary suitable for use in the Anthropic ``tools=`` parameter.
    """
    tool_name = name or func.__name__
    sig = inspect.signature(func)

    # Build description from docstring
    raw_doc = func.__doc__ or ""
    if description:
        tool_description = description
    else:
        # Use the first paragraph (up to the first blank line) as description
        lines = textwrap.dedent(raw_doc).strip().splitlines()
        desc_lines: list[str] = []
        for line in lines:
            if not line.strip():
                break
            desc_lines.append(line.strip())
        tool_description = " ".join(desc_lines) or f"Tool: {tool_name}"

    # Parse parameter descriptions from docstring
    param_descriptions = _parse_google_docstring_args(raw_doc)

    properties: dict[str, Any] = {}
    required: list[str] = []

    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls"):
            continue

        annotation = param.annotation
        if annotation is inspect.Parameter.empty:
            json_type = "string"
        else:
            json_type = _python_type_to_json_schema(annotation)

        prop: dict[str, Any] = {"type": json_type}

        # Add description if available from docstring
        if param_name in param_descriptions:
            prop["description"] = param_descriptions[param_name]

        properties[param_name] = prop

        # Parameters without defaults are required
        if param.default is inspect.Parameter.empty:
            required.append(param_name)

    return {
        "name": tool_name,
        "description": tool_description,
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }


class ToolWrapper:
    """Wrapper around a decorated tool function.

    Provides the original callable, tool metadata, and serialisation methods.
    Instances are callable and delegate to the wrapped function.

    Attributes:
        func: The original unwrapped function.
        strict: Whether Pydantic validation is enabled for inputs.
    """

    def __init__(
        self,
        func: Callable[..., Any],
        *,
        name: str | None = None,
        description: str | None = None,
        strict: bool = False,
    ) -> None:
        self.func = func
        self.strict = strict
        self._is_async = asyncio.iscoroutinefunction(func)
        self._definition = _build_tool_definition(func, name=name, description=description)

        # Preserve function metadata
        functools.update_wrapper(self, func)

        # Attach the tool definition as an attribute on the wrapper
        self.__tool_definition__ = self._definition

    @property
    def name(self) -> str:
        """The tool name as it appears in the Anthropic API."""
        return self._definition["name"]

    def to_dict(self) -> dict[str, Any]:
        """Return the Anthropic tool parameter dict.

        Returns:
            A dictionary ready for inclusion in the ``tools=`` list of an
            Anthropic API call.
        """
        return dict(self._definition)

    def _validate_inputs(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Validate and coerce inputs when strict mode is enabled.

        Args:
            kwargs: The keyword arguments to validate.

        Returns:
            The validated (and possibly coerced) keyword arguments.

        Raises:
            ToolInputValidationError: If validation fails.
        """
        if not self.strict:
            return kwargs

        from claudekit.tools._validator import ToolInputValidator

        validator = ToolInputValidator(self._definition["input_schema"])
        return validator.validate(self.name, kwargs)

    def _process_result(self, result: Any) -> Any:
        """Process the raw return value of the tool function.

        Converts ``None`` to ``""`` and logs a warning if the string result
        exceeds the warning threshold.

        Args:
            result: The raw return value from the tool function.

        Returns:
            The processed result.
        """
        if result is None:
            return ""

        if isinstance(result, str) and len(result) > _RESULT_WARNING_THRESHOLD:
            logger.warning(
                "Tool %r returned a string of %d characters, which exceeds the "
                "%d-character warning threshold. Consider reducing the output size.",
                self.name,
                len(result),
                _RESULT_WARNING_THRESHOLD,
            )

        return result

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Call the wrapped tool function.

        For sync functions, calls directly. For async functions in a sync
        context, raises ``RuntimeError`` with guidance.

        Args:
            *args: Positional arguments passed to the function.
            **kwargs: Keyword arguments passed to the function.

        Returns:
            The tool function's return value (with ``None`` converted to ``""``).

        Raises:
            RuntimeError: If an async tool is called from a sync context.
        """
        if self._is_async:
            # Check if there's a running event loop
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop is None:
                raise RuntimeError(
                    f"Async tool {self.name!r} cannot be called from a sync context. "
                    f"Use 'await {self.name}(...)' inside an async function, or use "
                    f"asyncio.run({self.name}(...)) to run it."
                )

            # We're inside an event loop, return the coroutine
            validated_kwargs = self._validate_inputs(kwargs)
            coro = self.func(*args, **validated_kwargs)

            async def _wrapper() -> Any:
                result = await coro
                return self._process_result(result)

            return _wrapper()

        validated_kwargs = self._validate_inputs(kwargs)
        result = self.func(*args, **validated_kwargs)
        return self._process_result(result)

    def __repr__(self) -> str:
        return f"<ToolWrapper name={self.name!r} strict={self.strict}>"


F = TypeVar("F", bound=Callable[..., Any])


@overload
def tool(func: F) -> ToolWrapper: ...


@overload
def tool(
    *,
    name: str | None = None,
    description: str | None = None,
    strict: bool = False,
) -> Callable[[F], ToolWrapper]: ...


def tool(
    func: F | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
    strict: bool = False,
) -> ToolWrapper | Callable[[F], ToolWrapper]:
    """Decorator that converts a Python function into an Anthropic tool.

    Can be used with or without arguments::

        @tool
        def my_tool(x: str) -> str:
            ...

        @tool(strict=True, name="custom_name")
        def another_tool(x: str) -> str:
            ...

    Args:
        func: The function to decorate (when used without parentheses).
        name: Override for the tool name. Defaults to the function name.
        description: Override for the tool description. Defaults to the
            first paragraph of the docstring.
        strict: If ``True``, enables Pydantic validation of inputs before
            the function is called.

    Returns:
        A :class:`ToolWrapper` instance that is callable and exposes tool
        metadata via ``.to_dict()`` and ``.name``.
    """
    if func is not None:
        # Used as @tool without parentheses
        return ToolWrapper(func, name=name, description=description, strict=strict)

    # Used as @tool(...) with arguments
    def decorator(fn: F) -> ToolWrapper:
        return ToolWrapper(fn, name=name, description=description, strict=strict)

    return decorator

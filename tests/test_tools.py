"""Tests for claudekit.tools -- @tool decorator and ToolWrapper."""

import pytest

from claudekit.tools._decorator import (
    ToolWrapper,
    _build_tool_definition,
    _parse_google_docstring_args,
    tool,
)


# ── Docstring parsing ────────────────────────────────────────────────────── #


class TestDocstringParsing:
    def test_parse_args_simple(self):
        docstring = "Do something.\n\nArgs:\n    city: The city name.\n    units: Temperature units.\n"
        result = _parse_google_docstring_args(docstring)
        assert result["city"] == "The city name."
        assert result["units"] == "Temperature units."

    def test_parse_args_none(self):
        assert _parse_google_docstring_args(None) == {}

    def test_parse_args_no_section(self):
        assert _parse_google_docstring_args("Just a description.") == {}

    def test_parse_args_multiline_desc(self):
        docstring = "Tool.\n\nArgs:\n    query: The search query to use\n        for looking things up.\n"
        result = _parse_google_docstring_args(docstring)
        assert "search query" in result["query"]
        assert "looking things up" in result["query"]


# ── @tool decorator ──────────────────────────────────────────────────────── #


class TestToolDecorator:
    def test_bare_decorator(self):
        @tool
        def greet(name: str) -> str:
            """Say hello."""
            return f"Hello, {name}!"

        assert isinstance(greet, ToolWrapper)
        assert greet.name == "greet"

    def test_decorator_with_args(self):
        @tool(name="custom_name", description="Custom desc")
        def greet(name: str) -> str:
            """Say hello."""
            return f"Hello, {name}!"

        assert greet.name == "custom_name"
        defn = greet.to_dict()
        assert defn["description"] == "Custom desc"

    def test_callable(self):
        @tool
        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        assert add(a=2, b=3) == 5

    def test_none_result_becomes_empty(self):
        @tool
        def noop() -> None:
            """Do nothing."""
            return None

        assert noop() == ""


# ── ToolWrapper ──────────────────────────────────────────────────────────── #


class TestToolWrapper:
    def test_to_dict_structure(self):
        @tool
        def search(query: str, limit: int = 10) -> str:
            """Search for items.

            Args:
                query: The search query.
                limit: Max results.
            """
            return ""

        defn = search.to_dict()
        assert defn["name"] == "search"
        assert "Search for items" in defn["description"]
        schema = defn["input_schema"]
        assert schema["type"] == "object"
        assert "query" in schema["properties"]
        assert "limit" in schema["properties"]
        assert "query" in schema["required"]
        assert "limit" not in schema["required"]

    def test_param_types(self):
        @tool
        def fn(a: str, b: int, c: float, d: bool, e: list, f: dict) -> str:
            """Fn."""
            return ""

        props = fn.to_dict()["input_schema"]["properties"]
        assert props["a"]["type"] == "string"
        assert props["b"]["type"] == "integer"
        assert props["c"]["type"] == "number"
        assert props["d"]["type"] == "boolean"
        assert props["e"]["type"] == "array"
        assert props["f"]["type"] == "object"

    def test_no_type_annotation_defaults_string(self):
        @tool
        def fn(x) -> str:
            """Fn."""
            return ""

        props = fn.to_dict()["input_schema"]["properties"]
        assert props["x"]["type"] == "string"

    def test_description_from_docstring(self):
        @tool
        def fn(x: str) -> str:
            """Get the weather forecast for a location.

            Args:
                x: Location name.
            """
            return ""

        defn = fn.to_dict()
        assert "weather forecast" in defn["description"]
        assert defn["input_schema"]["properties"]["x"]["description"] == "Location name."

    def test_repr(self):
        @tool
        def fn() -> str:
            """Fn."""
            return ""

        r = repr(fn)
        assert "ToolWrapper" in r
        assert "fn" in r

    def test_self_cls_excluded(self):
        def method(self, x: str) -> str:
            """M."""
            return ""

        defn = _build_tool_definition(method)
        assert "self" not in defn["input_schema"]["properties"]
        assert "x" in defn["input_schema"]["properties"]

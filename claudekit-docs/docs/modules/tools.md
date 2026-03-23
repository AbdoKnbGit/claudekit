# Tools

**Module:** `claudekit.tools` · **Classes:** `ToolWrapper`, `ToolRegistry`

`claudekit.tools` provides the `@tool` decorator, which converts Python functions into Anthropic-compatible tool definitions. It inspects type annotations and Google-style docstrings to build the JSON schema automatically.

## @tool decorator

```python
from claudekit.tools import tool

@tool
def get_weather(city: str, units: str = "celsius") -> str:
    """Get current weather for a city.

    Args:
        city: The city to look up weather for.
        units: Temperature units, either 'celsius' or 'fahrenheit'.

    Returns:
        A string describing the current weather.
    """
    return f"Sunny in {city}, 22°{units[0].upper()}"
```

This creates a `ToolWrapper` that:
- Is callable — call it like a normal function.
- Has `.to_dict()` — returns the Anthropic tool definition dict.
- Has `.name` — the tool name used in the API.

### With arguments

```python
@tool(name="custom_name", description="Override description", strict=True)
def my_func(x: int, y: int = 0) -> str:
    """Original docstring (ignored when description= is set)."""
    return str(x + y)
```

Parameters:
- `name` — override tool name (default: function name).
- `description` — override tool description (default: first paragraph of docstring).
- `strict` — if `True`, validates inputs against the schema with Pydantic before calling.

### Type mapping

| Python type | JSON Schema type |
| --- | --- |
| `str` | `"string"` |
| `int` | `"integer"` |
| `float` | `"number"` |
| `bool` | `"boolean"` |
| `list` / `list[T]` | `"array"` |
| `dict` | `"object"` |
| unannotated | `"string"` |

### Required vs optional

Parameters **without** defaults are marked `required` in the schema. Parameters **with** defaults are optional.

```python
@tool
def search(query: str, limit: int = 10) -> list:
    ...
# query is required, limit is optional
```

### Async tools

```python
@tool
async def fetch_url(url: str) -> str:
    """Fetch content from a URL."""
    import httpx
    async with httpx.AsyncClient() as client:
        r = await client.get(url)
        return r.text
```

Calling an async `ToolWrapper` outside an event loop raises `RuntimeError` with guidance. Inside an async context it returns a coroutine.

---

## ToolWrapper

The object returned by `@tool`.

```python
wrapper = get_weather   # the decorated function IS the ToolWrapper

wrapper.name            # str — "get_weather"
wrapper.func            # the original unwrapped function
wrapper.strict          # bool
wrapper.to_dict()       # dict — Anthropic tool definition
wrapper.__tool_definition__   # same as to_dict(), as an attribute

# Calling
result = wrapper(city="London")         # sync
result = await wrapper(city="London")   # inside async context (async tools)
```

### Example: passing tools to the API

```python
response = client.messages.create(
    model="claude-haiku-4-5",
    max_tokens=1024,
    tools=[get_weather.to_dict()],
    messages=[{"role": "user", "content": "What's the weather in Paris?"}],
)
```

Or let `Skill` handle this:

```python
skill = Skill(name="weather-skill", system="...", tools=[get_weather])
result = await skill.run(input="Paris weather?", client=client)
```

---

## ToolRegistry

Named registry for tool lookup, listing, and format conversion.

```python
from claudekit.tools import ToolRegistry

registry = ToolRegistry()
registry.register(get_weather)    # plain functions are auto-wrapped
registry.register(search_web)

tool = registry.get("get_weather")          # ToolWrapper | None
all_tools = registry.all()                  # list[ToolWrapper]
registry.remove("get_weather")
len(registry)                               # int

# Format conversion
registry.to_anthropic_format()              # list[dict] — for messages.create(tools=...)
registry.to_agent_sdk_format()              # list[str]  — tool names for Claude Agent SDK
```

---

## MCPServer

Serve your `@tool` functions as a Model Context Protocol server — compatible with Claude desktop apps and the Agent SDK.

```python
from claudekit.tools import MCPServer, tool

@tool
def add(a: int, b: int) -> str:
    """Add two numbers."""
    return str(a + b)

server = MCPServer("math_server", version="1.0.0")
server.add(add)

server.run()                  # blocking stdio server
server.run_background()       # launch in a subprocess, returns Popen

# Generate config for Claude Agent SDK's mcp_servers= parameter
opts = server.to_options_dict()
```

---

## Pre-built Tools

```python
from claudekit.tools.prebuilt import (
    # Web
    web_search,     # web_search(query: str, num_results: int = 5) -> str  (DuckDuckGo, no API key)
    web_fetch,      # web_fetch(url: str, extract_text: bool = True) -> str

    # Files
    read_file,      # read_file(path: str, encoding: str = "utf-8") -> str
    write_file,     # write_file(path: str, content: str, append: bool = False) -> str
    list_dir,       # list_dir(path: str = ".", pattern: str = "*") -> str
    file_exists,    # file_exists(path: str) -> str

    # Code execution
    run_python,     # run_python(code: str, timeout_seconds: int = 10) -> str
    run_bash,       # run_bash(command: str, timeout_seconds: int = 10) -> str

    # Data
    parse_json,     # parse_json(text: str) -> str
    parse_csv,      # parse_csv(text: str, delimiter: str = ",") -> str
    format_table,   # format_table(data: str, max_rows: int = 50) -> str
)
```

Each is a `@tool`-decorated function ready to pass to `Skill(tools=[...])` or directly to `messages.create(tools=[...])`.

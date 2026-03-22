# claudekit · tools

Tools (function calling) infrastructure for Anthropic Claude. Automatically generate JSON schemas from Python functions, manage registries, and serve tools via MCP.

**Source files:** `_decorator.py`, `_registry.py`, `_validator.py`, `_mcp_server.py`, `prebuilt/*`

---

## Core Components

### `@tool` Decorator
**Source:** `_decorator.py:344`
The primary way to define tools. It inspects signatures and Google-style docstrings to generate the Anthropic-compatible JSON schema.

```python
from claudekit.tools import tool

@tool(strict=True)
def get_order_status(order_id: int) -> str:
    """Get the current status of a customer order.

    Args:
        order_id: The numeric ID of the order.
    """
    return "Shipped"
```

- **Docstring Parsing:** Uses the first paragraph for the tool description and the `Args:` section for parameter descriptions.
- **Strict Mode:** If `strict=True`, inputs are validated and coerced by `ToolInputValidator` before the function is called.
- **Async Support:** Seamlessly supports both `def` and `async def` tool functions.

### `ToolRegistry`
**Source:** `_registry.py:37`
A container for managing sets of tools.

- **`register(tool_or_fn)`**: Adds a tool. Plain functions are auto-wrapped.
- **`to_anthropic_format()`**: Serialises to the `list[dict]` structure required by the Messages API.
- **`to_agent_sdk_format()`**: Serialises to a list of names for the Claude Agent SDK.

### `MCPServer`
**Source:** `_mcp_server.py:61`
Wraps tools into a Model Context Protocol (MCP) server.

- **`run()`**: Starts a blocking stdio server.
- **`run_background()`**: Launches the server in a separate process for use with desktop Claude apps.
- **`to_options_dict()`**: Generates configuration for the Claude Agent SDK's `mcp_servers` parameter.

---

## Prebuilt Tools

`claudekit` includes a collection of batteries-included tools for common agentic tasks.

### Code Execution (`prebuilt._code`)
- **`run_python(code, timeout_seconds=10)`**: Executes code in an isolated subprocess.
- **`run_bash(command, timeout_seconds=10, working_dir=".")`**: Executes shell commands.

### Data Processing (`prebuilt._data`)
- **`parse_json(text)`**: Safely parse JSON.
- **`parse_csv(text, delimiter=",")`**: Parse CSV into a list of dicts.
- **`format_table(data, max_rows=50)`**: Convert a list of dicts into a plain-text table optimized for LLM readability.

### File System (`prebuilt._files`)
- **`read_file(path, encoding="utf-8")`**: Read text files.
- **`write_file(path, content, append=False)`**: Write/append to files (auto-creates directories).
- **`list_dir(path=".", pattern="*")`**: List directory contents with globbing.
- **`file_exists(path)`**: Check if a path exists.

### Web (`prebuilt._web`)
- **`web_search(query, num_results=5)`**: Scrapes DuckDuckGo for search results (no API key required).
- **`web_fetch(url, extract_text=True)`**: Fetches a URL. If `extract_text` is True, it strips HTML tags and scripts to return clean prose.

---

## Technical Details

1. **Type Coercion.** When `strict=True` is used, `claudekit` attempts to coerce inputs to match annotations (e.g., string `"123"` to integer `123`).
2. **Async Context.** If an `async def` tool is called from a synchronous context without an active event loop, a `RuntimeError` is raised with guidance.
3. **Large Outputs.** Tool outputs exceeding 100,000 characters trigger a warning in logs, as very large outputs can degrade LLM performance or hit context limits.
4. **ToolResult Formatting.** `None` return values are automatically converted to empty strings (`""`) to satisfy API requirements.
5. **MCP Isolation.** `MCPServer.run_background()` generates a temporary runner script to ensure the environment matches the parent process.

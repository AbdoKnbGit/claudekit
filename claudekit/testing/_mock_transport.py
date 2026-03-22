"""Realistic zero-cost mock using ``httpx.MockTransport``.

Injects a fake HTTP transport directly into the Anthropic SDK client so the
**full SDK stack** runs — auth headers, retries, Pydantic validation, error
mapping — with absolutely zero network calls.

Example::

    from claudekit.testing import create_mock_anthropic

    client = create_mock_anthropic(
        default_reply="Hello from the mock!",
        patterns={"weather": "It is sunny."},
    )

    # This is a REAL anthropic.Anthropic — not a mock class.
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=100,
        messages=[{"role": "user", "content": "What is the weather?"}],
    )
    assert response.content[0].text == "It is sunny."
    assert response.model == "claude-haiku-4-5"
    assert response.usage.input_tokens > 0
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any, Callable

import httpx

from claudekit._defaults import DEFAULT_FAST_MODEL

logger = logging.getLogger(__name__)


# ── Response JSON builders ───────────────────────────────────────────────── #


def _message_json(
    text: str,
    model: str = DEFAULT_FAST_MODEL,
    *,
    input_tokens: int = 25,
    output_tokens: int | None = None,
    stop_reason: str = "end_turn",
    tool_use: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a valid Anthropic ``Message`` JSON payload.

    Returns a dict that passes the SDK's Pydantic validation when parsed as
    an ``anthropic.types.Message``.
    """
    content: list[dict[str, Any]] = []
    if text:
        content.append({"type": "text", "text": text})
    if tool_use:
        for tu in tool_use:
            content.append({
                "type": "tool_use",
                "id": tu.get("id", f"toolu_{uuid.uuid4().hex[:20]}"),
                "name": tu["name"],
                "input": tu.get("input", {}),
            })

    if output_tokens is None:
        output_tokens = max(1, len(text.split()) * 2)

    return {
        "id": f"msg_{uuid.uuid4().hex[:24]}",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": content,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        },
    }


def _error_json(status: int, error_type: str, message: str) -> dict[str, Any]:
    """Build an Anthropic-style error JSON body."""
    return {
        "type": "error",
        "error": {"type": error_type, "message": message},
    }


def _count_tokens_json(input_tokens: int = 100) -> dict[str, Any]:
    """Build a count_tokens response payload."""
    return {"input_tokens": input_tokens}


# ── SSE helpers for streaming ────────────────────────────────────────────── #


def _sse_bytes(events: list[dict[str, Any]]) -> bytes:
    """Encode a list of SSE events as bytes for streaming responses."""
    lines: list[str] = []
    for event in events:
        lines.append(f"event: {event['event']}")
        lines.append(f"data: {json.dumps(event['data'])}")
        lines.append("")
    return "\n".join(lines).encode("utf-8")


def _streaming_events(
    text: str,
    model: str = DEFAULT_FAST_MODEL,
    *,
    chunks: list[str] | None = None,
    input_tokens: int = 25,
) -> list[dict[str, Any]]:
    """Build a list of SSE events that simulate a streaming response."""
    if chunks is None:
        chunks = [text]

    output_tokens = max(1, len(text.split()) * 2)
    msg_id = f"msg_{uuid.uuid4().hex[:24]}"

    events = [
        {
            "event": "message_start",
            "data": {
                "type": "message_start",
                "message": {
                    "id": msg_id,
                    "type": "message",
                    "role": "assistant",
                    "model": model,
                    "content": [],
                    "stop_reason": None,
                    "stop_sequence": None,
                    "usage": {"input_tokens": input_tokens, "output_tokens": 0},
                },
            },
        },
        {
            "event": "content_block_start",
            "data": {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "text", "text": ""},
            },
        },
    ]

    for chunk in chunks:
        events.append({
            "event": "content_block_delta",
            "data": {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": chunk},
            },
        })

    events.extend([
        {
            "event": "content_block_stop",
            "data": {"type": "content_block_stop", "index": 0},
        },
        {
            "event": "message_delta",
            "data": {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                "usage": {"output_tokens": output_tokens},
            },
        },
        {
            "event": "message_stop",
            "data": {"type": "message_stop"},
        },
    ])

    return events


# ── MockTransportHandler ─────────────────────────────────────────────────── #


class MockTransportHandler:
    """HTTP request handler for ``httpx.MockTransport``.

    Maps incoming API requests to pre-configured responses based on pattern
    matching against the last user message content.

    Args:
        patterns: Dict mapping substring patterns to reply text.
        default_reply: Fallback reply when no pattern matches.
        token_count: Default token count for ``count_tokens`` endpoint.
        stream_patterns: Dict mapping substring patterns to list of chunks.
        error_patterns: Dict mapping substring patterns to (status, error_type, message).
        tool_patterns: Dict mapping substring patterns to tool_use dicts.
    """

    def __init__(
        self,
        *,
        patterns: dict[str, str] | None = None,
        default_reply: str = "Mock response",
        token_count: int = 100,
        stream_patterns: dict[str, list[str]] | None = None,
        error_patterns: dict[str, tuple[int, str, str]] | None = None,
        tool_patterns: dict[str, list[dict[str, Any]]] | None = None,
    ) -> None:
        self._patterns: list[tuple[str, str]] = list((patterns or {}).items())
        self._default_reply = default_reply
        self._token_count = token_count
        self._stream_patterns: dict[str, list[str]] = stream_patterns or {}
        self._error_patterns: dict[str, tuple[int, str, str]] = error_patterns or {}
        self._tool_patterns: dict[str, list[dict[str, Any]]] = tool_patterns or {}
        self.calls: list[dict[str, Any]] = []

    def _extract_last_user_content(self, body: dict[str, Any]) -> str:
        """Pull the text of the last user message from the request body."""
        messages = body.get("messages", [])
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    return content
                if isinstance(content, list):
                    parts = [
                        b.get("text", "") for b in content if b.get("type") == "text"
                    ]
                    return " ".join(parts)
        return ""

    def _match(self, user_text: str) -> str | None:
        """Find first matching pattern (most recently added wins via reversal)."""
        for pattern, reply in reversed(self._patterns):
            if pattern.lower() in user_text.lower():
                return reply
        return None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        """Handle an HTTP request from the SDK."""
        path = request.url.path

        body_bytes = request.content if hasattr(request, "content") else b"{}"
        try:
            body = json.loads(body_bytes) if body_bytes else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            body = {}

        self.calls.append({"path": path, "body": body})

        # ── Count tokens endpoint ────────────────────────────────────── #
        if "/count_tokens" in path:
            return httpx.Response(
                status_code=200,
                json=_count_tokens_json(self._token_count),
                headers={"content-type": "application/json", "request-id": f"req_{uuid.uuid4().hex[:12]}"},
            )

        # ── Messages endpoint ────────────────────────────────────────── #
        if "/messages" in path:
            model = body.get("model", DEFAULT_FAST_MODEL)
            user_text = self._extract_last_user_content(body)
            stream = body.get("stream", False)

            # Check error patterns first
            for pat, (status, err_type, err_msg) in self._error_patterns.items():
                if pat.lower() in user_text.lower():
                    return httpx.Response(
                        status_code=status,
                        json=_error_json(status, err_type, err_msg),
                        headers={"content-type": "application/json", "request-id": f"req_{uuid.uuid4().hex[:12]}"},
                    )

            # Check tool patterns
            for pat, tools in self._tool_patterns.items():
                if pat.lower() in user_text.lower():
                    reply_json = _message_json("", model, tool_use=tools, stop_reason="tool_use")
                    return httpx.Response(
                        status_code=200,
                        json=reply_json,
                        headers={"content-type": "application/json", "request-id": f"req_{uuid.uuid4().hex[:12]}"},
                    )

            # Check stream patterns
            if stream:
                for pat, chunks in self._stream_patterns.items():
                    if pat.lower() in user_text.lower():
                        text = "".join(chunks)
                        events = _streaming_events(text, model, chunks=chunks)
                        return httpx.Response(
                            status_code=200,
                            content=_sse_bytes(events),
                            headers={
                                "content-type": "text/event-stream",
                                "request-id": f"req_{uuid.uuid4().hex[:12]}",
                            },
                        )
                # Default stream
                events = _streaming_events(self._default_reply, model)
                return httpx.Response(
                    status_code=200,
                    content=_sse_bytes(events),
                    headers={
                        "content-type": "text/event-stream",
                        "request-id": f"req_{uuid.uuid4().hex[:12]}",
                    },
                )

            # Text patterns (non-streaming)
            reply = self._match(user_text) or self._default_reply
            reply_json = _message_json(reply, model)
            return httpx.Response(
                status_code=200,
                json=reply_json,
                headers={"content-type": "application/json", "request-id": f"req_{uuid.uuid4().hex[:12]}"},
            )

        # ── Fallback for unknown endpoints ───────────────────────────── #
        return httpx.Response(
            status_code=404,
            json=_error_json(404, "not_found_error", f"Unknown path: {path}"),
            headers={"content-type": "application/json"},
        )

    # ── Registration helpers ─────────────────────────────────────────── #

    def on(self, pattern: str, reply: str) -> None:
        """Register a text pattern → reply mapping."""
        self._patterns.append((pattern, reply))

    def on_error(self, pattern: str, status: int, error_type: str, message: str) -> None:
        """Register a pattern that triggers an SDK error."""
        self._error_patterns[pattern] = (status, error_type, message)

    def on_tool(self, pattern: str, tool_name: str, tool_input: dict[str, Any] | None = None) -> None:
        """Register a pattern that triggers a tool_use response."""
        if pattern not in self._tool_patterns:
            self._tool_patterns[pattern] = []
        self._tool_patterns[pattern].append({
            "name": tool_name,
            "input": tool_input or {},
        })

    def on_stream(self, pattern: str, chunks: list[str]) -> None:
        """Register a pattern that triggers a streaming response."""
        self._stream_patterns[pattern] = chunks


# ── Factory ──────────────────────────────────────────────────────────────── #


def create_mock_anthropic(
    *,
    api_key: str = "sk-ant-test-fake-key",
    default_reply: str = "Mock response",
    patterns: dict[str, str] | None = None,
    token_count: int = 100,
    stream_patterns: dict[str, list[str]] | None = None,
    error_patterns: dict[str, tuple[int, str, str]] | None = None,
    tool_patterns: dict[str, list[dict[str, Any]]] | None = None,
    handler: MockTransportHandler | None = None,
) -> tuple[Any, MockTransportHandler]:
    """Create a real ``anthropic.Anthropic`` backed by ``httpx.MockTransport``.

    The returned client has the **full SDK stack running**: auth headers,
    retry logic, Pydantic model validation, error mapping — everything
    except actual network calls.

    Args:
        api_key: Fake API key (SDK requires one to instantiate).
        default_reply: Fallback text when no pattern matches.
        patterns: Dict of substring patterns → reply text.
        token_count: Token count returned by ``count_tokens``.
        stream_patterns: Dict of patterns → list of streaming chunks.
        error_patterns: Dict of patterns → ``(status, error_type, message)`` tuples.
        tool_patterns: Dict of patterns → list of tool_use dicts.
        handler: Pre-built handler (overrides all other pattern args).

    Returns:
        A ``(client, handler)`` tuple. The handler exposes ``.calls`` for
        inspection and ``.on()`` / ``.on_error()`` / ``.on_tool()`` /
        ``.on_stream()`` for further registration after creation.

    Example::

        client, handler = create_mock_anthropic(
            patterns={"hello": "Hi there!"},
        )
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=100,
            messages=[{"role": "user", "content": "hello world"}],
        )
        assert response.content[0].text == "Hi there!"
        assert len(handler.calls) == 1
    """
    import anthropic as _anthropic

    if handler is None:
        handler = MockTransportHandler(
            patterns=patterns,
            default_reply=default_reply,
            token_count=token_count,
            stream_patterns=stream_patterns,
            error_patterns=error_patterns,
            tool_patterns=tool_patterns,
        )

    mock_transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=mock_transport)

    client = _anthropic.Anthropic(
        api_key=api_key,
        http_client=http_client,
    )

    return client, handler


__all__ = [
    "MockTransportHandler",
    "create_mock_anthropic",
]

"""Mock client for zero-API testing.

Provides :class:`MockClient`, a drop-in replacement for
:class:`~claudekit.client.TrackedClient` that produces genuine
:class:`anthropic.types.Message` instances via ``construct()`` without
making any network calls.

Pattern matching, streaming simulation, tool-call mocking, and security
layer integration are all supported.
"""

from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from typing import Any, Iterator, Optional

import anthropic
import anthropic.types

from claudekit._defaults import DEFAULT_FAST_MODEL
from claudekit.client._session import CallRecord, SessionUsage

logger = logging.getLogger(__name__)


# =========================================================================== #
# Errors
# =========================================================================== #

class MockClientUnexpectedCallError(Exception):
    """Raised when a MockClient in strict mode receives an unmatched call."""

    def __init__(self, message: str, *, kwargs: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.kwargs = kwargs or {}


# =========================================================================== #
# Mock streaming support
# =========================================================================== #

class _MockStreamEvent:
    """A single server-sent event in a mock stream."""

    def __init__(self, event_type: str, data: Any) -> None:
        self.type = event_type
        self.data = data


class MockStreamContext:
    """Context manager that mimics the SDK's ``MessageStream``.

    Yields text-delta events for each chunk, then exposes a
    ``get_final_message()`` returning a proper :class:`anthropic.types.Message`.

    Args:
        chunks: List of text strings to yield as deltas.
        model: Model identifier for the final message.
        kwargs: Original request kwargs for metadata.
    """

    def __init__(self, chunks: list[str], model: str, kwargs: dict[str, Any]) -> None:
        self._chunks = chunks
        self._model = model
        self._kwargs = kwargs
        self._final_message: anthropic.types.Message | None = None
        self._entered = False

    def __enter__(self) -> MockStreamContext:
        self._entered = True
        full_text = "".join(self._chunks)
        self._final_message = _build_text_message(full_text, self._model, self._kwargs)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass

    def __iter__(self) -> Iterator[_MockStreamEvent]:
        if not self._entered:
            raise RuntimeError("MockStreamContext must be used as a context manager")
        for chunk in self._chunks:
            yield _MockStreamEvent("content_block_delta", {"type": "text_delta", "text": chunk})

    def get_final_message(self) -> anthropic.types.Message:
        """Return the final assembled message, matching SDK stream behaviour."""
        if self._final_message is None:
            raise RuntimeError("Stream has not been consumed")
        return self._final_message

    @property
    def text(self) -> str:
        """Convenience property returning the full concatenated text."""
        return "".join(self._chunks)


# =========================================================================== #
# Token count result
# =========================================================================== #

class _TokenCountResult:
    """Simple object returned by ``count_tokens()``."""

    def __init__(self, input_tokens: int) -> None:
        self.input_tokens = input_tokens

    def __repr__(self) -> str:
        return f"TokenCountResult(input_tokens={self.input_tokens})"


# =========================================================================== #
# Message builders
# =========================================================================== #

def _build_text_message(
    text: str, model: str, kwargs: dict[str, Any]
) -> anthropic.types.Message:
    """Build a genuine ``anthropic.types.Message`` with a text content block.

    Uses ``construct()`` to bypass Pydantic validation, allowing creation
    without a live API connection.

    Args:
        text: The assistant's reply text.
        model: Model identifier.
        kwargs: Original request kwargs for metadata extraction.

    Returns:
        A fully-formed ``anthropic.types.Message``.
    """
    msg_id = f"msg_mock_{int(time.time() * 1000)}"
    return anthropic.types.Message.construct(
        id=msg_id,
        type="message",
        role="assistant",
        content=[anthropic.types.TextBlock(type="text", text=text)],
        model=kwargs.get("model", model),
        stop_reason="end_turn",
        usage=anthropic.types.Usage(
            input_tokens=10,
            output_tokens=max(1, len(text.split())),
        ),
    )


def _build_tool_use_message(
    tool_name: str,
    tool_input: dict[str, Any],
    model: str,
    kwargs: dict[str, Any],
) -> anthropic.types.Message:
    """Build a genuine ``anthropic.types.Message`` with a tool_use content block.

    Args:
        tool_name: The tool name to invoke.
        tool_input: The tool input dictionary.
        model: Model identifier.
        kwargs: Original request kwargs for metadata extraction.

    Returns:
        A ``Message`` with a single ``ToolUseBlock``.
    """
    msg_id = f"msg_mock_{int(time.time() * 1000)}"
    return anthropic.types.Message.construct(
        id=msg_id,
        type="message",
        role="assistant",
        content=[
            anthropic.types.ToolUseBlock(
                type="tool_use",
                id=f"toolu_mock_{int(time.time() * 1000)}",
                name=tool_name,
                input=tool_input,
            )
        ],
        model=kwargs.get("model", model),
        stop_reason="tool_use",
        usage=anthropic.types.Usage(input_tokens=10, output_tokens=5),
    )


# =========================================================================== #
# Helpers
# =========================================================================== #

def _extract_last_user_content(kwargs: dict[str, Any]) -> str:
    """Extract the text content of the last user message from request kwargs.

    Handles both simple string content and list-of-blocks content formats.

    Args:
        kwargs: The request keyword arguments containing ``messages``.

    Returns:
        The text content of the last user message, or an empty string.
    """
    messages = kwargs.get("messages", [])
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts: list[str] = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        parts.append(block.get("text", ""))
                    elif isinstance(block, str):
                        parts.append(block)
                return " ".join(parts)
            return str(content)
    return ""


# =========================================================================== #
# MockMessages
# =========================================================================== #

class MockMessages:
    """Mock messages namespace mimicking ``client.messages``.

    Supports ``create()``, ``stream()``, and ``count_tokens()`` with pattern-based
    response routing and optional security layer integration.

    Args:
        mock_client: The parent :class:`MockClient` instance.
    """

    def __init__(self, mock_client: MockClient) -> None:
        self._client = mock_client

    def create(self, **kwargs: Any) -> anthropic.types.Message:
        """Create a mock message response.

        Records the call, applies security checks if configured, and returns
        a genuine ``anthropic.types.Message`` built from the matching pattern.

        Args:
            **kwargs: Arguments that would normally be forwarded to the
                Anthropic ``messages.create()`` endpoint.

        Returns:
            An ``anthropic.types.Message`` instance.

        Raises:
            MockClientUnexpectedCallError: If strict mode is enabled and no
                pattern matches.
        """
        client = self._client
        model = kwargs.get("model", DEFAULT_FAST_MODEL)

        # Record the call
        client._calls.append(dict(kwargs))
        logger.debug("MockClient.messages.create() called (call #%d)", len(client._calls))

        # Security: check request
        if client.security is not None:
            messages = kwargs.get("messages", [])
            client.security.check_request(messages, model=model)

        # Find matching pattern (most recently registered first)
        user_content = _extract_last_user_content(kwargs)
        matched = None
        for pattern_entry in reversed(client._patterns):
            pattern = pattern_entry["pattern"]
            if pattern in user_content:
                matched = pattern_entry
                break

        # Build response
        if matched is not None:
            if "error" in matched and matched["error"] is not None:
                raise matched["error"](f"Mock error triggered by pattern {matched['pattern']!r}")

            if "chunks" in matched and matched["chunks"] is not None:
                # Streaming pattern used with create() -- concatenate chunks
                full_text = "".join(matched["chunks"])
                response = _build_text_message(full_text, model, kwargs)
            elif "tool_call" in matched and matched["tool_call"] is not None:
                tc = matched["tool_call"]
                response = _build_tool_use_message(tc["name"], tc["input"], model, kwargs)
            elif "reply" in matched and matched["reply"] is not None:
                response = _build_text_message(matched["reply"], model, kwargs)
            else:
                response = _build_text_message("", model, kwargs)
        elif client._default_reply is not None:
            response = _build_text_message(client._default_reply, model, kwargs)
        elif client.strict:
            raise MockClientUnexpectedCallError(
                f"No pattern matched user content {user_content!r} and no default_reply is set. "
                f"Registered patterns: {[p['pattern'] for p in client._patterns]}",
                kwargs=kwargs,
            )
        else:
            response = _build_text_message("", model, kwargs)

        # Record usage
        usage = getattr(response, "usage", None)
        if usage is not None:
            record = CallRecord(
                model=model,
                input_tokens=getattr(usage, "input_tokens", 0),
                output_tokens=getattr(usage, "output_tokens", 0),
                estimated_cost=0.0,
            )
            client._usage.record(record)

        # Security: check response
        if client.security is not None:
            response = client.security.check_response(response, model=model)

        return response

    def stream(self, **kwargs: Any) -> MockStreamContext:
        """Create a mock streaming response.

        Returns a context manager that yields text-delta events for each
        chunk registered via :meth:`MockClient.on_stream`.

        Args:
            **kwargs: Arguments that would normally be forwarded to
                ``messages.stream()``.

        Returns:
            A :class:`MockStreamContext` usable as a context manager.

        Raises:
            MockClientUnexpectedCallError: If strict mode is enabled and no
                streaming pattern matches.
        """
        client = self._client
        model = kwargs.get("model", DEFAULT_FAST_MODEL)

        # Record the call
        client._calls.append(dict(kwargs))
        logger.debug("MockClient.messages.stream() called (call #%d)", len(client._calls))

        # Security: check request
        if client.security is not None:
            messages = kwargs.get("messages", [])
            client.security.check_request(messages, model=model)

        # Find matching pattern
        user_content = _extract_last_user_content(kwargs)
        matched = None
        for pattern_entry in reversed(client._patterns):
            pattern = pattern_entry["pattern"]
            if pattern in user_content:
                matched = pattern_entry
                break

        if matched is not None:
            if "error" in matched and matched["error"] is not None:
                raise matched["error"](f"Mock error triggered by pattern {matched['pattern']!r}")

            if "chunks" in matched and matched["chunks"] is not None:
                chunks = matched["chunks"]
            elif "reply" in matched and matched["reply"] is not None:
                chunks = [matched["reply"]]
            else:
                chunks = [""]
        elif client._default_reply is not None:
            chunks = [client._default_reply]
        elif client.strict:
            raise MockClientUnexpectedCallError(
                f"No pattern matched user content {user_content!r} for streaming. "
                f"Registered patterns: {[p['pattern'] for p in client._patterns]}",
                kwargs=kwargs,
            )
        else:
            chunks = [""]

        return MockStreamContext(chunks, model, kwargs)

    def count_tokens(self, **kwargs: Any) -> _TokenCountResult:
        """Mock token counting.

        Returns a result object with the ``input_tokens`` value configured
        via :meth:`MockClient.mock_token_count`.

        Args:
            **kwargs: Arguments that would normally be forwarded to the
                token counting endpoint.

        Returns:
            A :class:`_TokenCountResult` with the configured token count.
        """
        logger.debug("MockClient.messages.count_tokens() called")
        return _TokenCountResult(self._client._token_count)


# =========================================================================== #
# MockBatches
# =========================================================================== #

class MockBatches:
    """Mock batches namespace for batch API simulation.

    Stores batch requests in memory and returns mock results on retrieval.
    """

    def __init__(self) -> None:
        self._batches: dict[str, dict[str, Any]] = {}
        self._counter = 0

    def create(self, **kwargs: Any) -> dict[str, Any]:
        """Create a mock batch.

        Args:
            **kwargs: Batch creation arguments.

        Returns:
            A dict representing the batch with an ``id`` and ``status``.
        """
        self._counter += 1
        batch_id = f"batch_mock_{self._counter}"
        batch = {
            "id": batch_id,
            "status": "completed",
            "created_at": time.time(),
            "kwargs": kwargs,
        }
        self._batches[batch_id] = batch
        logger.debug("MockBatches.create() -> %s", batch_id)
        return batch

    def retrieve(self, batch_id: str) -> dict[str, Any] | None:
        """Retrieve a mock batch by ID.

        Args:
            batch_id: The batch identifier.

        Returns:
            The batch dict, or ``None`` if not found.
        """
        return self._batches.get(batch_id)

    def results(self, batch_id: str) -> list[dict[str, Any]]:
        """Retrieve mock batch results.

        Args:
            batch_id: The batch identifier.

        Returns:
            An empty list (override in subclass for custom results).
        """
        logger.debug("MockBatches.results(%s) called", batch_id)
        return []

    def cancel(self, batch_id: str) -> dict[str, Any] | None:
        """Cancel a mock batch.

        Args:
            batch_id: The batch identifier.

        Returns:
            The updated batch dict with status ``"cancelled"``, or ``None``.
        """
        batch = self._batches.get(batch_id)
        if batch is not None:
            batch["status"] = "cancelled"
            logger.debug("MockBatches.cancel(%s) -> cancelled", batch_id)
        return batch


# =========================================================================== #
# MockClient
# =========================================================================== #

class MockClient:
    """Drop-in replacement for :class:`~claudekit.client.TrackedClient` with zero API calls.

    Produces genuine :class:`anthropic.types.Message` instances using
    ``construct()``.  Supports pattern matching, streaming mocks, tool call
    simulation, and optional security layer integration.

    Args:
        strict: If ``True`` (default), raises :class:`MockClientUnexpectedCallError`
            when no pattern matches an incoming call.
        security: Optional :class:`~claudekit.security.SecurityLayer` to apply
            request/response checks.

    Example::

        >>> client = MockClient()
        >>> client.on("hello", "Hi there!")
        >>> response = client.messages.create(
        ...     model="claude-haiku-4-5",
        ...     max_tokens=100,
        ...     messages=[{"role": "user", "content": "hello"}],
        ... )
        >>> assert response.content[0].text == "Hi there!"
    """

    def __init__(
        self,
        strict: bool = True,
        security: Any = None,
    ) -> None:
        self.strict = strict
        self.security = security
        self.messages = MockMessages(self)
        self._patterns: list[dict[str, Any]] = []
        self._default_reply: str | None = None
        self._calls: list[dict[str, Any]] = []
        self._token_count: int = 100
        self._usage = SessionUsage()
        self._batches = MockBatches()

        logger.debug(
            "MockClient created (strict=%s, security=%s)",
            strict,
            security is not None,
        )

    # ------------------------------------------------------------------ #
    # Pattern registration
    # ------------------------------------------------------------------ #

    def on(
        self,
        pattern: str,
        reply: str | None = None,
        tool_call: dict[str, Any] | None = None,
    ) -> None:
        """Register a pattern match.

        Pattern is a substring match against the last user message content.
        Most recently registered patterns take priority.

        Args:
            pattern: Substring to match against user content.
            reply: Text reply to return when matched.
            tool_call: Optional dict with ``name`` and ``input`` keys for
                tool_use responses.
        """
        self._patterns.append({
            "pattern": pattern,
            "reply": reply,
            "tool_call": tool_call,
            "chunks": None,
            "error": None,
        })
        logger.debug("MockClient.on(%r) registered", pattern)

    def on_tool(self, pattern: str, tool_name: str, tool_input: dict[str, Any]) -> None:
        """Register a ``tool_use`` response for a pattern.

        Args:
            pattern: Substring to match against user content.
            tool_name: The tool name in the response.
            tool_input: The tool input dictionary.
        """
        self._patterns.append({
            "pattern": pattern,
            "reply": None,
            "tool_call": {"name": tool_name, "input": tool_input},
            "chunks": None,
            "error": None,
        })
        logger.debug("MockClient.on_tool(%r, %r) registered", pattern, tool_name)

    def on_stream(self, pattern: str, chunks: list[str]) -> None:
        """Register a streaming response for a pattern.

        Args:
            pattern: Substring to match against user content.
            chunks: List of text strings to yield as stream deltas.
        """
        self._patterns.append({
            "pattern": pattern,
            "reply": None,
            "tool_call": None,
            "chunks": list(chunks),
            "error": None,
        })
        logger.debug("MockClient.on_stream(%r, %d chunks) registered", pattern, len(chunks))

    def on_error(self, pattern: str, error_class: type) -> None:
        """Register an error response for a pattern.

        When the pattern matches, the specified exception class will be
        raised instead of returning a message.

        Args:
            pattern: Substring to match against user content.
            error_class: Exception class to instantiate and raise.
        """
        self._patterns.append({
            "pattern": pattern,
            "reply": None,
            "tool_call": None,
            "chunks": None,
            "error": error_class,
        })
        logger.debug("MockClient.on_error(%r, %s) registered", pattern, error_class.__name__)

    def default_reply(self, text: str) -> None:
        """Set the fallback reply used when no pattern matches.

        Args:
            text: Default text to return.
        """
        self._default_reply = text
        logger.debug("MockClient default_reply set to %r", text[:80])

    def mock_token_count(self, input_tokens: int = 100) -> None:
        """Set the return value for ``count_tokens()``.

        Args:
            input_tokens: The token count to return.
        """
        self._token_count = input_tokens

    # ------------------------------------------------------------------ #
    # Call inspection
    # ------------------------------------------------------------------ #

    @property
    def calls(self) -> list[dict[str, Any]]:
        """Return a copy of all recorded calls.

        Returns:
            List of kwargs dicts from each ``create()`` or ``stream()`` call.
        """
        return list(self._calls)

    @property
    def call_count(self) -> int:
        """Return the number of calls made so far.

        Returns:
            Integer count of calls.
        """
        return len(self._calls)

    @property
    def usage(self) -> SessionUsage:
        """The :class:`SessionUsage` tracker for mock calls.

        Returns:
            The session usage tracker.
        """
        return self._usage

    @property
    def batches(self) -> MockBatches:
        """The mock batches namespace.

        Returns:
            The :class:`MockBatches` instance.
        """
        return self._batches

    # ------------------------------------------------------------------ #
    # Assertions on calls
    # ------------------------------------------------------------------ #

    def assert_called(self) -> None:
        """Assert that at least one call was made.

        Raises:
            AssertionError: If no calls have been recorded.
        """
        if not self._calls:
            raise AssertionError("MockClient was never called")

    def assert_not_called(self) -> None:
        """Assert that no calls were made.

        Raises:
            AssertionError: If any calls have been recorded.
        """
        if self._calls:
            raise AssertionError(
                f"MockClient was called {len(self._calls)} time(s), expected 0"
            )

    def assert_called_with(self, pattern: str) -> None:
        """Assert that a message matching *pattern* was sent.

        Searches through all recorded calls for a user message containing
        the given substring.

        Args:
            pattern: Substring to search for in user message content.

        Raises:
            AssertionError: If no call contained a message matching the pattern.
        """
        for call in self._calls:
            msgs = call.get("messages", [])
            for msg in msgs:
                content = msg.get("content", "")
                if isinstance(content, str) and pattern in content:
                    return
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and pattern in block.get("text", ""):
                            return
                        if isinstance(block, str) and pattern in block:
                            return
        raise AssertionError(
            f"No call matched pattern {pattern!r}. "
            f"Total calls: {len(self._calls)}"
        )

    def assert_call_count(self, expected: int) -> None:
        """Assert exactly *expected* calls were made.

        Args:
            expected: Expected number of calls.

        Raises:
            AssertionError: If the actual count differs.
        """
        actual = len(self._calls)
        if actual != expected:
            raise AssertionError(
                f"Expected {expected} call(s), got {actual}"
            )

    def assert_call_order(self, patterns: list[str]) -> None:
        """Assert calls were made in the given order.

        Extracts user message content from calls and verifies that the
        given patterns appear as substrings in order.

        Args:
            patterns: Ordered list of substrings to match.

        Raises:
            AssertionError: If the call order does not match.
        """
        call_contents: list[str] = []
        for call in self._calls:
            msgs = call.get("messages", [])
            for msg in msgs:
                if msg.get("role") == "user":
                    content = msg.get("content", "")
                    if isinstance(content, str):
                        call_contents.append(content)
                    elif isinstance(content, list):
                        parts = []
                        for block in content:
                            if isinstance(block, dict):
                                parts.append(block.get("text", ""))
                            elif isinstance(block, str):
                                parts.append(block)
                        call_contents.append(" ".join(parts))

        pattern_idx = 0
        for content in call_contents:
            if pattern_idx < len(patterns) and patterns[pattern_idx] in str(content):
                pattern_idx += 1
        if pattern_idx < len(patterns):
            raise AssertionError(
                f"Call order mismatch. Expected patterns: {patterns}, "
                f"Got user contents: {call_contents}"
            )

    def assert_model_used(self, model: str) -> None:
        """Assert that a specific model was used in at least one call.

        Args:
            model: Model identifier to search for.

        Raises:
            AssertionError: If the model was not used.
        """
        for call in self._calls:
            if call.get("model") == model:
                return
        raise AssertionError(
            f"Model {model!r} was never used. "
            f"Models used: {[c.get('model') for c in self._calls]}"
        )

    # ------------------------------------------------------------------ #
    # Reset
    # ------------------------------------------------------------------ #

    def reset(self) -> None:
        """Clear all recorded calls and registered patterns.

        Resets the mock client to its initial state while preserving
        configuration (strict mode, security layer).
        """
        self._calls.clear()
        self._patterns.clear()
        self._default_reply = None
        self._usage = SessionUsage()
        logger.debug("MockClient reset")

    def reset_calls(self) -> None:
        """Clear only recorded calls, keeping registered patterns.

        Useful for verifying behaviour across multiple test phases.
        """
        self._calls.clear()
        self._usage = SessionUsage()
        logger.debug("MockClient calls reset (patterns preserved)")

    # ------------------------------------------------------------------ #
    # Proxy compatibility
    # ------------------------------------------------------------------ #

    def with_options(self, **kwargs: Any) -> MockClient:
        """Return self for API compatibility with :class:`TrackedClient`.

        Args:
            **kwargs: Ignored.

        Returns:
            This same :class:`MockClient` instance.
        """
        return self

    def __repr__(self) -> str:
        return (
            f"MockClient(strict={self.strict}, patterns={len(self._patterns)}, "
            f"calls={len(self._calls)})"
        )


__all__ = [
    "MockClient",
    "MockClientUnexpectedCallError",
    "MockMessages",
    "MockBatches",
    "MockStreamContext",
]

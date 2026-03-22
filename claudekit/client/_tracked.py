"""Tracked wrapper around :class:`anthropic.Anthropic`.

Intercepts ``messages.create()`` and ``messages.stream()`` to record token
usage, estimated costs, and timing information in a :class:`SessionUsage`
instance.  The wrapper uses composition -- it holds a reference to the real
SDK client and proxies attribute access -- so it never interferes with SDK
internals such as timeout behaviour or stream lifecycle.
"""

from __future__ import annotations

import logging
import time
import warnings
from typing import Any, Iterator, Optional

import anthropic

from claudekit.client._session import CallRecord, SessionUsage
from claudekit.errors._rich import DeprecatedModelWarning
from claudekit.models import get_model

logger = logging.getLogger(__name__)


def _extract_usage(response: Any) -> tuple[int, int, int, int]:
    """Extract token counts from an API response.

    Returns:
        Tuple of (input_tokens, output_tokens, cache_read_tokens, cache_write_tokens).
    """
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0, 0, 0, 0
    input_tokens = getattr(usage, "input_tokens", 0) or 0
    output_tokens = getattr(usage, "output_tokens", 0) or 0
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
    return input_tokens, output_tokens, cache_read, cache_write


def _extract_request_id(response: Any) -> str:
    """Extract the API request ID from a response, if available."""
    # The SDK attaches _request_id on API responses
    req_id = getattr(response, "_request_id", None)
    if req_id:
        return str(req_id)
    return ""


def _estimate_cost(
    model_id: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int,
    cache_write_tokens: int,
    is_batch: bool = False,
) -> float:
    """Estimate call cost in USD using the model registry.

    Args:
        model_id: API model identifier.
        input_tokens: Input token count.
        output_tokens: Output token count.
        cache_read_tokens: Cache-read token count.
        cache_write_tokens: Cache-write token count.
        is_batch: Whether this is a batch call (50% discount).

    Returns:
        Estimated cost in USD.
    """
    model = get_model(model_id)
    if model is None:
        logger.debug("Unknown model %r for cost estimation; returning 0.0", model_id)
        return 0.0
    cost = model.estimate_cost(input_tokens, output_tokens, cache_read_tokens, cache_write_tokens)
    if is_batch:
        cost *= 0.5
    return cost


def _check_deprecated(model_id: str) -> None:
    """Emit a :class:`DeprecatedModelWarning` if *model_id* is deprecated."""
    model = get_model(model_id)
    if model is not None and model.is_deprecated:
        msg = f"Model {model_id!r} is deprecated"
        if model.eol_date:
            msg += f" (EOL {model.eol_date})"
        if model.recommended_replacement:
            msg += f". Consider switching to {model.recommended_replacement!r}"
        msg += "."
        warnings.warn(msg, DeprecatedModelWarning, stacklevel=2)
        logger.warning(msg)


class _TrackedMessages:
    """Proxy for ``client.messages`` that records usage on every call.

    This inner class wraps the real ``messages`` resource from the Anthropic
    SDK, intercepting ``create()`` and ``stream()`` to capture token usage,
    cost, and timing metadata.

    Args:
        messages: The real ``client.messages`` resource.
        usage: The :class:`SessionUsage` tracker to record calls into.
    """

    def __init__(self, messages: Any, usage: SessionUsage) -> None:
        self._messages = messages
        self._usage = usage

    def create(self, **kwargs: Any) -> Any:
        """Call ``messages.create()`` and record usage.

        All keyword arguments are forwarded to the underlying SDK method.
        Usage is recorded after a successful response.  Exceptions propagate
        unmodified so SDK timeout behaviour (``MODEL_NONSTREAMING_TOKENS``)
        and other error handling remain intact.

        Args:
            **kwargs: Arguments forwarded to ``anthropic.Anthropic().messages.create()``.

        Returns:
            The API response (``anthropic.types.Message``).
        """
        model_id = kwargs.get("model", "")
        _check_deprecated(model_id)

        idempotency_key = kwargs.pop("idempotency_key", "") or ""

        start = time.perf_counter()
        response = self._messages.create(**kwargs)
        duration_ms = (time.perf_counter() - start) * 1000.0

        input_tokens, output_tokens, cache_read, cache_write = _extract_usage(response)
        request_id = _extract_request_id(response)

        cost = _estimate_cost(
            model_id, input_tokens, output_tokens, cache_read, cache_write,
        )

        record = CallRecord(
            model=model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read,
            cache_write_tokens=cache_write,
            estimated_cost=cost,
            request_id=request_id,
            idempotency_key=idempotency_key,
            duration_ms=duration_ms,
        )
        self._usage.record(record)

        logger.debug(
            "Recorded call: model=%s in=%d out=%d cost=$%.6f dur=%.0fms",
            model_id, input_tokens, output_tokens, cost, duration_ms,
        )
        return response

    def stream(self, **kwargs: Any) -> Any:
        """Call ``messages.stream()`` and record usage when the stream closes.

        Returns the SDK stream context manager directly.  Usage is recorded
        from the ``get_final_message()`` after the stream is consumed.  If the
        stream is not fully consumed (e.g., ``StreamAlreadyConsumed`` is raised),
        the exception propagates without interference.

        Args:
            **kwargs: Arguments forwarded to ``anthropic.Anthropic().messages.stream()``.

        Returns:
            A stream context manager (``MessageStream``).
        """
        model_id = kwargs.get("model", "")
        _check_deprecated(model_id)

        idempotency_key = kwargs.pop("idempotency_key", "") or ""
        usage = self._usage

        start = time.perf_counter()
        raw_stream = self._messages.stream(**kwargs)

        class _TrackedStreamWrapper:
            """Thin wrapper that records usage when the stream context exits."""

            def __init__(self, inner: Any) -> None:
                self._inner = inner
                self._entered = False

            def __enter__(self) -> Any:
                self._entered = True
                self._stream = self._inner.__enter__()
                return self._stream

            def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Any:
                result = self._inner.__exit__(exc_type, exc_val, exc_tb)
                # Only record usage if the stream was consumed successfully
                if exc_type is None:
                    try:
                        final_msg = self._stream.get_final_message()
                        duration_ms = (time.perf_counter() - start) * 1000.0
                        input_tokens, output_tokens, cache_read, cache_write = (
                            _extract_usage(final_msg)
                        )
                        request_id = _extract_request_id(final_msg)
                        cost = _estimate_cost(
                            model_id, input_tokens, output_tokens,
                            cache_read, cache_write,
                        )
                        record = CallRecord(
                            model=model_id,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            cache_read_tokens=cache_read,
                            cache_write_tokens=cache_write,
                            estimated_cost=cost,
                            request_id=request_id,
                            idempotency_key=idempotency_key,
                            duration_ms=duration_ms,
                        )
                        usage.record(record)
                        logger.debug(
                            "Recorded stream call: model=%s in=%d out=%d cost=$%.6f",
                            model_id, input_tokens, output_tokens, cost,
                        )
                    except (AttributeError, KeyError, TypeError, ValueError):
                        logger.debug(
                            "Could not extract final message from stream for usage tracking",
                            exc_info=True,
                        )
                return result

            def __getattr__(self, name: str) -> Any:
                return getattr(self._inner, name)

        return _TrackedStreamWrapper(raw_stream)

    def __getattr__(self, name: str) -> Any:
        """Proxy all other attribute access to the underlying messages resource."""
        return getattr(self._messages, name)


class TrackedClient:
    """Usage-tracking wrapper around :class:`anthropic.Anthropic`.

    Intercepts ``messages.create()`` and ``messages.stream()`` to record
    token usage, estimated costs, and timing metadata.  All other SDK
    functionality is proxied through transparently.

    Args:
        api_key: Anthropic API key.  Falls back to ``ANTHROPIC_API_KEY`` env var.
        security: Optional :class:`~claudekit.security.SecurityLayer` instance.
        memory: Optional :class:`~claudekit.memory.MemoryStore` instance.
        usage: Optional shared :class:`SessionUsage`.  If ``None``, a new one
            is created.
        **kwargs: Additional keyword arguments forwarded to
            :class:`anthropic.Anthropic`.

    Example::

        from claudekit.client import TrackedClient

        client = TrackedClient(api_key="sk-...")
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1024,
            messages=[{"role": "user", "content": "Hello!"}],
        )
        print(client.usage.summary())
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        security: Any = None,
        memory: Any = None,
        usage: Optional[SessionUsage] = None,
        **kwargs: Any,
    ) -> None:
        client_kwargs: dict[str, Any] = dict(kwargs)
        if api_key is not None:
            client_kwargs["api_key"] = api_key

        self._client = anthropic.Anthropic(**client_kwargs)
        self._usage = usage if usage is not None else SessionUsage()
        self._sessions: list[SessionUsage] = []
        self._security = security
        self._memory = memory

        self._messages = _TrackedMessages(self._client.messages, self._usage)

    @property
    def usage(self) -> SessionUsage:
        """The :class:`SessionUsage` tracker for this client."""
        return self._usage

    @property
    def security(self) -> Any:
        """The optional security layer attached to this client."""
        return self._security

    @property
    def memory(self) -> Any:
        """The optional memory store attached to this client."""
        return self._memory

    @property
    def messages(self) -> _TrackedMessages:
        """The tracked messages resource (wraps ``client.messages``)."""
        return self._messages

    def create_session(self) -> SessionUsage:
        """Create a new inline session with its own :class:`SessionUsage`.

        The session shares the same underlying API client but tracks usage
        independently.  The session's usage is also included in
        :attr:`all_sessions_usage`.

        Returns:
            A fresh :class:`SessionUsage` instance for the new session.
        """
        session_usage = SessionUsage()
        self._sessions.append(session_usage)
        return session_usage

    @property
    def all_sessions_usage(self) -> SessionUsage:
        """Combined view of usage across the main tracker and all sessions.

        Returns a new :class:`SessionUsage` that aggregates all calls from the
        primary usage tracker and every session created via
        :meth:`create_session`.
        """
        combined = SessionUsage()
        for call in self._usage.calls:
            combined.record(call)
        for session in self._sessions:
            for call in session.calls:
                combined.record(call)
        return combined

    def with_options(self, **kwargs: Any) -> TrackedClient:
        """Return a new :class:`TrackedClient` sharing the same :class:`SessionUsage`.

        This is useful for adjusting per-request defaults (e.g., timeout) while
        keeping a unified usage view.

        Args:
            **kwargs: Options forwarded to the underlying SDK's
                ``with_options()`` method.

        Returns:
            A new :class:`TrackedClient` that shares this client's
            :class:`SessionUsage`.
        """
        new_inner = self._client.with_options(**kwargs)
        new_client = object.__new__(TrackedClient)
        new_client._client = new_inner
        new_client._usage = self._usage
        new_client._sessions = self._sessions
        new_client._security = self._security
        new_client._memory = self._memory
        new_client._messages = _TrackedMessages(new_inner.messages, self._usage)
        return new_client

    def __getattr__(self, name: str) -> Any:
        """Proxy attribute access to the underlying :class:`anthropic.Anthropic` client."""
        return getattr(self._client, name)

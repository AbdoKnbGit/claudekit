"""Tracked wrapper around :class:`anthropic.AsyncAnthropic`.

Async counterpart of :mod:`._tracked`.  Intercepts ``messages.create()`` and
``messages.stream()`` to record token usage, estimated costs, and timing in
a shared :class:`SessionUsage` instance.
"""

from __future__ import annotations

import logging
import time
import warnings
from typing import Any, Optional

import anthropic

from claudekit.client._session import CallRecord, SessionUsage
from claudekit.client._tracked import (
    DeprecatedModelWarning,
    _check_deprecated,
    _estimate_cost,
    _extract_request_id,
    _extract_usage,
)

logger = logging.getLogger(__name__)


class _AsyncTrackedMessages:
    """Async proxy for ``client.messages`` that records usage on every call.

    Args:
        messages: The real async ``client.messages`` resource.
        usage: The :class:`SessionUsage` tracker to record calls into.
    """

    def __init__(self, messages: Any, usage: SessionUsage) -> None:
        self._messages = messages
        self._usage = usage

    async def create(self, **kwargs: Any) -> Any:
        """Call ``messages.create()`` asynchronously and record usage.

        All keyword arguments are forwarded to the underlying SDK method.

        Args:
            **kwargs: Arguments forwarded to
                ``anthropic.AsyncAnthropic().messages.create()``.

        Returns:
            The API response (``anthropic.types.Message``).
        """
        model_id = kwargs.get("model", "")
        _check_deprecated(model_id)

        idempotency_key = kwargs.pop("idempotency_key", "") or ""

        start = time.perf_counter()
        response = await self._messages.create(**kwargs)
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
            "Recorded async call: model=%s in=%d out=%d cost=$%.6f dur=%.0fms",
            model_id, input_tokens, output_tokens, cost, duration_ms,
        )
        return response

    async def stream(self, **kwargs: Any) -> Any:
        """Call ``messages.stream()`` asynchronously and record usage on close.

        Returns the SDK async stream context manager.  Usage is recorded from
        the ``get_final_message()`` after the stream is consumed.

        Args:
            **kwargs: Arguments forwarded to
                ``anthropic.AsyncAnthropic().messages.stream()``.

        Returns:
            An async stream context manager (``AsyncMessageStream``).
        """
        model_id = kwargs.get("model", "")
        _check_deprecated(model_id)

        idempotency_key = kwargs.pop("idempotency_key", "") or ""
        usage = self._usage

        start = time.perf_counter()
        raw_stream = self._messages.stream(**kwargs)

        class _AsyncTrackedStreamWrapper:
            """Thin async wrapper that records usage when the stream exits."""

            def __init__(self, inner: Any) -> None:
                self._inner = inner
                self._stream: Any = None

            async def __aenter__(self) -> Any:
                self._stream = await self._inner.__aenter__()
                return self._stream

            async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Any:
                result = await self._inner.__aexit__(exc_type, exc_val, exc_tb)
                if exc_type is None and self._stream is not None:
                    try:
                        final_msg = await self._stream.get_final_message()
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
                            "Recorded async stream call: model=%s in=%d out=%d cost=$%.6f",
                            model_id, input_tokens, output_tokens, cost,
                        )
                    except (AttributeError, KeyError, TypeError, ValueError):
                        logger.debug(
                            "Could not extract final message from async stream "
                            "for usage tracking",
                            exc_info=True,
                        )
                return result

            def __getattr__(self, name: str) -> Any:
                return getattr(self._inner, name)

        return _AsyncTrackedStreamWrapper(raw_stream)

    def __getattr__(self, name: str) -> Any:
        """Proxy all other attribute access to the underlying messages resource."""
        return getattr(self._messages, name)


class AsyncTrackedClient:
    """Usage-tracking wrapper around :class:`anthropic.AsyncAnthropic`.

    Async counterpart of :class:`TrackedClient`.  Intercepts
    ``messages.create()`` and ``messages.stream()`` to record token usage,
    estimated costs, and timing metadata.  All other SDK functionality is
    proxied through transparently.

    Args:
        api_key: Anthropic API key.  Falls back to ``ANTHROPIC_API_KEY`` env var.
        security: Optional security layer instance.
        memory: Optional memory store instance.
        usage: Optional shared :class:`SessionUsage`.  If ``None``, a new one
            is created.
        http_client: Optional ``httpx.AsyncClient`` to use for HTTP requests.
            Passed through to the underlying :class:`anthropic.AsyncAnthropic`.
        **kwargs: Additional keyword arguments forwarded to
            :class:`anthropic.AsyncAnthropic`.

    Example::

        import asyncio
        from claudekit.client import AsyncTrackedClient

        async def main():
            client = AsyncTrackedClient(api_key="sk-...")
            response = await client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=1024,
                messages=[{"role": "user", "content": "Hello!"}],
            )
            print(client.usage.summary())

        asyncio.run(main())
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        security: Any = None,
        memory: Any = None,
        usage: Optional[SessionUsage] = None,
        http_client: Any = None,
        **kwargs: Any,
    ) -> None:
        client_kwargs: dict[str, Any] = dict(kwargs)
        if api_key is not None:
            client_kwargs["api_key"] = api_key
        if http_client is not None:
            client_kwargs["http_client"] = http_client

        self._client = anthropic.AsyncAnthropic(**client_kwargs)
        self._usage = usage if usage is not None else SessionUsage()
        self._sessions: list[SessionUsage] = []
        self._security = security
        self._memory = memory

        self._messages = _AsyncTrackedMessages(self._client.messages, self._usage)

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
    def messages(self) -> _AsyncTrackedMessages:
        """The tracked messages resource (wraps ``client.messages``)."""
        return self._messages

    def create_session(self) -> SessionUsage:
        """Create a new inline session with its own :class:`SessionUsage`.

        Returns:
            A fresh :class:`SessionUsage` instance for the new session.
        """
        session_usage = SessionUsage()
        self._sessions.append(session_usage)
        return session_usage

    @property
    def all_sessions_usage(self) -> SessionUsage:
        """Combined view of usage across the main tracker and all sessions."""
        combined = SessionUsage()
        for call in self._usage.calls:
            combined.record(call)
        for session in self._sessions:
            for call in session.calls:
                combined.record(call)
        return combined

    def with_options(self, **kwargs: Any) -> AsyncTrackedClient:
        """Return a new :class:`AsyncTrackedClient` sharing the same :class:`SessionUsage`.

        Args:
            **kwargs: Options forwarded to the underlying SDK's
                ``with_options()`` method.

        Returns:
            A new :class:`AsyncTrackedClient` sharing usage tracking state.
        """
        new_inner = self._client.with_options(**kwargs)
        new_client = object.__new__(AsyncTrackedClient)
        new_client._client = new_inner
        new_client._usage = self._usage
        new_client._sessions = self._sessions
        new_client._security = self._security
        new_client._memory = self._memory
        new_client._messages = _AsyncTrackedMessages(new_inner.messages, self._usage)
        return new_client

    def __getattr__(self, name: str) -> Any:
        """Proxy attribute access to the underlying async client."""
        return getattr(self._client, name)

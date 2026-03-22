"""Tracked wrapper around :class:`anthropic.AnthropicVertex`.

Provides the same usage-tracking interface as :class:`TrackedClient` but
backed by the Google Vertex AI client.  The ``anthropic[vertex]`` extra must
be installed; if it is missing, instantiation raises
:class:`~claudekit.errors.PlatformNotAvailableError`.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from claudekit.client._session import CallRecord, SessionUsage
from claudekit.client._tracked import (
    _check_deprecated,
    _estimate_cost,
    _extract_request_id,
    _extract_usage,
)

logger = logging.getLogger(__name__)


def _get_vertex_class() -> type:
    """Lazily import and return :class:`anthropic.AnthropicVertex`.

    Raises:
        claudekit.errors.PlatformNotAvailableError: If ``anthropic[vertex]``
            is not installed.
    """
    try:
        from anthropic import AnthropicVertex
        return AnthropicVertex
    except (ImportError, AttributeError):
        from claudekit.errors import PlatformNotAvailableError
        raise PlatformNotAvailableError(
            message=(
                "Package 'anthropic[vertex]' is required for Google Vertex AI support. "
                "Install it with: pip install anthropic[vertex]"
            ),
            recovery_hint="pip install anthropic[vertex]",
        )


class _VertexTrackedMessages:
    """Proxy for Vertex ``client.messages`` that records usage.

    Args:
        messages: The real Vertex ``client.messages`` resource.
        usage: The :class:`SessionUsage` tracker.
    """

    def __init__(self, messages: Any, usage: SessionUsage) -> None:
        self._messages = messages
        self._usage = usage

    def create(self, **kwargs: Any) -> Any:
        """Call ``messages.create()`` on Vertex and record usage.

        Args:
            **kwargs: Arguments forwarded to the underlying SDK method.

        Returns:
            The API response.
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
            "Recorded Vertex call: model=%s in=%d out=%d cost=$%.6f dur=%.0fms",
            model_id, input_tokens, output_tokens, cost, duration_ms,
        )
        return response

    def stream(self, **kwargs: Any) -> Any:
        """Call ``messages.stream()`` on Vertex and record usage on close.

        Args:
            **kwargs: Arguments forwarded to the underlying SDK method.

        Returns:
            A stream context manager.
        """
        model_id = kwargs.get("model", "")
        _check_deprecated(model_id)

        idempotency_key = kwargs.pop("idempotency_key", "") or ""
        usage = self._usage

        start = time.perf_counter()
        raw_stream = self._messages.stream(**kwargs)

        class _VertexStreamWrapper:
            def __init__(self, inner: Any) -> None:
                self._inner = inner
                self._stream: Any = None

            def __enter__(self) -> Any:
                self._stream = self._inner.__enter__()
                return self._stream

            def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Any:
                result = self._inner.__exit__(exc_type, exc_val, exc_tb)
                if exc_type is None and self._stream is not None:
                    try:
                        final_msg = self._stream.get_final_message()
                        duration_ms = (time.perf_counter() - start) * 1000.0
                        inp, out, cr, cw = _extract_usage(final_msg)
                        req_id = _extract_request_id(final_msg)
                        cost = _estimate_cost(model_id, inp, out, cr, cw)
                        record = CallRecord(
                            model=model_id,
                            input_tokens=inp,
                            output_tokens=out,
                            cache_read_tokens=cr,
                            cache_write_tokens=cw,
                            estimated_cost=cost,
                            request_id=req_id,
                            idempotency_key=idempotency_key,
                            duration_ms=duration_ms,
                        )
                        usage.record(record)
                        logger.debug(
                            "Recorded Vertex stream: model=%s in=%d out=%d cost=$%.6f",
                            model_id, inp, out, cost,
                        )
                    except (AttributeError, KeyError, TypeError, ValueError):
                        logger.debug(
                            "Could not extract final message from Vertex stream",
                            exc_info=True,
                        )
                return result

            def __getattr__(self, name: str) -> Any:
                return getattr(self._inner, name)

        return _VertexStreamWrapper(raw_stream)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._messages, name)


class TrackedVertexClient:
    """Usage-tracking wrapper around :class:`anthropic.AnthropicVertex`.

    Provides the same ``messages.create()`` / ``messages.stream()`` tracking
    interface as :class:`TrackedClient`, but backed by the Google Vertex AI
    client.

    Args:
        security: Optional security layer instance.
        memory: Optional memory store instance.
        usage: Optional shared :class:`SessionUsage`.
        **kwargs: Keyword arguments forwarded to
            :class:`anthropic.AnthropicVertex` (e.g., ``project_id``,
            ``region``).

    Raises:
        claudekit.errors.PlatformNotAvailableError: If ``anthropic[vertex]``
            is not installed.

    Example::

        from claudekit.client import TrackedVertexClient

        client = TrackedVertexClient(
            project_id="my-project",
            region="us-east5",
        )
        response = client.messages.create(
            model="claude-haiku-4-5@20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": "Hello!"}],
        )
        print(client.usage.summary())
    """

    def __init__(
        self,
        *,
        security: Any = None,
        memory: Any = None,
        usage: Optional[SessionUsage] = None,
        **kwargs: Any,
    ) -> None:
        cls = _get_vertex_class()
        self._client = cls(**kwargs)
        self._usage = usage if usage is not None else SessionUsage()
        self._sessions: list[SessionUsage] = []
        self._security = security
        self._memory = memory
        self._messages = _VertexTrackedMessages(self._client.messages, self._usage)

    @property
    def usage(self) -> SessionUsage:
        """The :class:`SessionUsage` tracker for this client."""
        return self._usage

    @property
    def security(self) -> Any:
        return self._security

    @property
    def memory(self) -> Any:
        return self._memory

    @property
    def messages(self) -> _VertexTrackedMessages:
        """The tracked messages resource."""
        return self._messages

    def create_session(self) -> SessionUsage:
        """Create a new inline session with its own :class:`SessionUsage`."""
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

    def with_options(self, **kwargs: Any) -> TrackedVertexClient:
        """Return a new client sharing the same :class:`SessionUsage`.

        Args:
            **kwargs: Options forwarded to the underlying SDK's
                ``with_options()`` method.

        Returns:
            A new :class:`TrackedVertexClient` sharing usage tracking state.
        """
        new_inner = self._client.with_options(**kwargs)
        new_client = object.__new__(TrackedVertexClient)
        new_client._client = new_inner
        new_client._usage = self._usage
        new_client._sessions = self._sessions
        new_client._security = self._security
        new_client._memory = self._memory
        new_client._messages = _VertexTrackedMessages(new_inner.messages, self._usage)
        return new_client

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)

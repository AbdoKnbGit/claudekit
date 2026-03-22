"""Record and replay API responses for CI testing.

:class:`ResponseRecorder` captures real API responses during development and
replays them deterministically in CI — zero API calls, zero cost, but with
real response shapes.

Example — record::

    from claudekit.testing import ResponseRecorder

    recorder = ResponseRecorder()
    with recorder.record_mode("fixtures/responses.json"):
        response = client.messages.create(model="claude-haiku-4-5", ...)
        # response is recorded to disk

Example — replay::

    with recorder.replay_mode("fixtures/responses.json") as mock_client:
        response = mock_client.messages.create(model="claude-haiku-4-5", ...)
        # response is loaded from disk, zero API calls
"""

from __future__ import annotations

import hashlib
import json
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

logger = logging.getLogger(__name__)


def _hash_request(kwargs: dict[str, Any]) -> str:
    """Create a deterministic hash of request kwargs for matching."""
    # Normalize: sort keys, use consistent JSON serialization
    serialized = json.dumps(kwargs, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


class _RecordingProxy:
    """Proxy that records create() calls and their responses."""

    def __init__(self, original_messages: Any, recordings: list[dict[str, Any]]) -> None:
        self._original = original_messages
        self._recordings = recordings

    def create(self, **kwargs: Any) -> Any:
        """Call the real API and record the response."""
        response = self._original.create(**kwargs)

        # Serialize the response
        response_data: dict[str, Any] = {}
        if hasattr(response, "model_dump"):
            response_data = response.model_dump()
        elif hasattr(response, "to_dict"):
            response_data = response.to_dict()
        else:
            response_data = {
                "id": getattr(response, "id", ""),
                "model": getattr(response, "model", ""),
                "content": str(getattr(response, "content", "")),
            }

        request_hash = _hash_request(kwargs)
        self._recordings.append({
            "request_hash": request_hash,
            "request": _serialize_request(kwargs),
            "response": response_data,
        })

        logger.debug("Recorded response for hash %s", request_hash)
        return response


class _ReplayMessages:
    """Proxy that replays responses from recorded data."""

    def __init__(self, recordings: list[dict[str, Any]]) -> None:
        self._recordings = recordings
        self._index = 0

    def create(self, **kwargs: Any) -> Any:
        """Return a recorded response without making any API call."""
        import anthropic.types

        request_hash = _hash_request(kwargs)

        # Try hash match first
        for rec in self._recordings:
            if rec["request_hash"] == request_hash:
                return anthropic.types.Message.model_validate(rec["response"])

        # Fall back to sequential replay
        if self._index < len(self._recordings):
            rec = self._recordings[self._index]
            self._index += 1
            logger.debug(
                "Replaying response %d (no hash match for %s, using sequential)",
                self._index - 1,
                request_hash,
            )
            return anthropic.types.Message.model_validate(rec["response"])

        raise RuntimeError(
            f"ResponseRecorder: no recorded response for request hash {request_hash}. "
            f"{len(self._recordings)} recordings available, {self._index} already consumed."
        )


class _ReplayClient:
    """A minimal client-like object that replays recorded responses."""

    def __init__(self, recordings: list[dict[str, Any]]) -> None:
        self.messages = _ReplayMessages(recordings)


def _serialize_request(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Serialize request kwargs to JSON-safe dict."""
    serialized: dict[str, Any] = {}
    for key, value in kwargs.items():
        try:
            json.dumps(value, default=str)
            serialized[key] = value
        except (TypeError, ValueError):
            serialized[key] = str(value)
    return serialized


class ResponseRecorder:
    """Record and replay API responses.

    Records real API responses to a JSON file during development, then
    replays them in CI without making any API calls.
    """

    def __init__(self) -> None:
        self._recordings: list[dict[str, Any]] = []

    @contextmanager
    def record_mode(self, path: str | Path) -> Generator[None, None, None]:
        """Context manager that records all responses to *path*.

        Patches are not used — the recorder wraps the client's messages object.
        Use the yielded value as a proxy, or call this after setting up the
        recording proxy.

        Args:
            path: File path to save recordings (JSON format).

        Example::

            recorder = ResponseRecorder()
            with recorder.record_mode("responses.json"):
                # client.messages is now wrapped to record
                response = client.messages.create(...)
        """
        self._recordings = []
        try:
            yield
        finally:
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._recordings, f, indent=2, default=str)
            logger.info("Recorded %d responses to %s", len(self._recordings), path)

    @contextmanager
    def replay_mode(self, path: str | Path) -> Generator[_ReplayClient, None, None]:
        """Context manager that replays recorded responses from *path*.

        Args:
            path: File path to load recordings from (JSON format).

        Yields:
            A client-like object whose ``messages.create()`` returns
            recorded responses.

        Example::

            recorder = ResponseRecorder()
            with recorder.replay_mode("responses.json") as replay_client:
                response = replay_client.messages.create(
                    model="claude-haiku-4-5",
                    max_tokens=100,
                    messages=[{"role": "user", "content": "hello"}],
                )
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(
                f"No recording file found at {path}. "
                f"Run with record_mode() first to capture responses."
            )

        with open(path, "r", encoding="utf-8") as f:
            recordings = json.load(f)

        logger.info("Replaying %d responses from %s", len(recordings), path)
        yield _ReplayClient(recordings)

    def wrap_client(self, client: Any) -> _RecordingProxy:
        """Wrap a client's messages object for recording.

        Returns a proxy whose ``create()`` calls through to the real client
        and records the response.

        Args:
            client: An ``anthropic.Anthropic`` or ``TrackedClient`` instance.

        Returns:
            A proxy object with a ``create()`` method.
        """
        return _RecordingProxy(client.messages, self._recordings)


__all__ = ["ResponseRecorder"]

"""Batch submission and lifecycle manager.

:class:`BatchManager` wraps the Anthropic Message Batches API, providing
submission, polling with exponential backoff, cancellation, and sidecar
persistence of batch IDs.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from claudekit.batches._builder import BatchBuilder
from claudekit.batches._result import BatchResult, BatchStats
from claudekit.client._session import CallRecord, SessionUsage
from claudekit.errors import (
    BatchCancelledError,
    BatchNotReadyError,
    BatchPartialFailureError,
    ConfigurationError,
)

logger = logging.getLogger(__name__)

# Default sidecar file location
_DEFAULT_SIDECAR = Path.home() / ".claudekit" / "batches.json"


class BatchManager:
    """Manages batch submission, polling, and result retrieval.

    Parameters
    ----------
    client:
        A :class:`~claudekit.client.TrackedClient` (or raw
        :class:`anthropic.Anthropic`) instance.
    usage:
        Optional :class:`SessionUsage` to record batch costs into (at 50%
        rate).  If ``None``, a new tracker is created.
    sidecar_path:
        Path to a JSON file for persisting batch IDs.  Set to ``None`` to
        disable persistence.

    Example
    -------
    ::

        from claudekit.client import TrackedClient
        from claudekit.batches import BatchManager, BatchBuilder

        client = TrackedClient()
        bm = BatchManager(client)

        builder = (
            BatchBuilder()
            .add("r1", [{"role": "user", "content": "Hello"}])
            .add("r2", [{"role": "user", "content": "World"}])
        )
        batch_id = bm.submit_builder(builder)
        result = await bm.wait(batch_id)
        print(result.stats.summary())
    """

    def __init__(
        self,
        client: Any,
        *,
        usage: Optional[SessionUsage] = None,
        sidecar_path: Optional[Path] = _DEFAULT_SIDECAR,
    ) -> None:
        self._client = client
        self._usage = usage if usage is not None else SessionUsage()
        self._sidecar_path = sidecar_path
        self._batch_ids: List[str] = []

        # Guard: .batches was added in anthropic SDK >= 0.30.0
        raw = getattr(client, "_client", client)
        if not hasattr(raw, "batches"):
            raise NotImplementedError(
                "BatchManager requires anthropic SDK >= 0.30.0 "
                "(current SDK does not expose .batches). "
                "Run: pip install --upgrade anthropic"
            )

        # Load existing batch IDs from sidecar
        if self._sidecar_path is not None:
            self._load_sidecar()

    # ------------------------------------------------------------------
    # Submission
    # ------------------------------------------------------------------

    def submit(
        self,
        requests: List[Dict[str, Any]],
        max_tokens: Optional[int] = None,
    ) -> str:
        """Submit a batch of requests to the API.

        Args:
            requests: List of batch request dicts, each with ``custom_id``
                and ``params``.
            max_tokens: If provided, override ``max_tokens`` in each request
                that does not already specify it.

        Returns:
            The batch ID string.

        Raises:
            ConfigurationError: If *requests* is empty.
        """
        if not requests:
            raise ConfigurationError(
                "Cannot submit an empty batch.",
                code="CONFIGURATION_ERROR",
                recovery_hint="Add at least one request before submitting.",
            )

        if max_tokens is not None:
            for req in requests:
                req.setdefault("params", {}).setdefault("max_tokens", max_tokens)

        logger.info("Submitting batch with %d requests", len(requests))
        response = self._client.batches.create(requests=requests)
        batch_id: str = response.id

        self._batch_ids.append(batch_id)
        self._save_sidecar()
        logger.info("Batch submitted: %s", batch_id)
        return batch_id

    def submit_builder(self, builder: BatchBuilder) -> str:
        """Submit a batch from a :class:`BatchBuilder`.

        Args:
            builder: A populated :class:`BatchBuilder` instance.

        Returns:
            The batch ID string.
        """
        return self.submit(builder.build())

    # ------------------------------------------------------------------
    # Polling / waiting
    # ------------------------------------------------------------------

    async def wait(
        self,
        batch_id: str,
        poll_interval: float = 30.0,
        max_wait: float = 86400.0,
    ) -> BatchResult:
        """Wait for a batch to complete, polling with exponential backoff.

        Args:
            batch_id: The batch ID to wait for.
            poll_interval: Initial poll interval in seconds.
            max_wait: Maximum total wait time in seconds (default 24 hours).

        Returns:
            A :class:`BatchResult` with entries and stats.

        Raises:
            BatchCancelledError: If the batch was cancelled.
            BatchNotReadyError: If *max_wait* is exceeded.
        """
        start = time.monotonic()
        interval = poll_interval
        max_interval = poll_interval * 8  # Cap exponential growth

        while True:
            elapsed = time.monotonic() - start
            if elapsed >= max_wait:
                raise BatchNotReadyError(
                    f"Batch {batch_id} not ready after {elapsed:.0f}s.",
                    context={"batch_id": batch_id, "elapsed_seconds": elapsed},
                )

            status = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._client.batches.retrieve(batch_id)
            )
            processing_status = getattr(status, "processing_status", None)

            logger.debug(
                "Batch %s status: %s (elapsed %.0fs)",
                batch_id,
                processing_status,
                elapsed,
            )

            if processing_status == "ended":
                return await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self._collect_results(batch_id, status)
                )

            if processing_status == "canceling":
                # Wait a bit to see if it fully cancels
                await asyncio.sleep(min(interval, 5.0))
                continue

            # Exponential backoff
            await asyncio.sleep(interval)
            interval = min(interval * 1.5, max_interval)

    # ------------------------------------------------------------------
    # Cancellation
    # ------------------------------------------------------------------

    def cancel(self, batch_id: str) -> None:
        """Request cancellation of a batch.

        Args:
            batch_id: The batch to cancel.
        """
        logger.info("Cancelling batch %s", batch_id)
        self._client.batches.cancel(batch_id)

    # ------------------------------------------------------------------
    # Usage
    # ------------------------------------------------------------------

    @property
    def usage(self) -> SessionUsage:
        """The :class:`SessionUsage` tracker for batch operations."""
        return self._usage

    # ------------------------------------------------------------------
    # Sidecar persistence
    # ------------------------------------------------------------------

    def _load_sidecar(self) -> None:
        """Load batch IDs from the sidecar JSON file."""
        if self._sidecar_path is None or not self._sidecar_path.exists():
            return
        try:
            data = json.loads(self._sidecar_path.read_text(encoding="utf-8"))
            self._batch_ids = data.get("batch_ids", [])
            logger.debug(
                "Loaded %d batch IDs from sidecar %s",
                len(self._batch_ids),
                self._sidecar_path,
            )
        except (json.JSONDecodeError, OSError, KeyError, TypeError):
            logger.debug(
                "Could not load sidecar file %s", self._sidecar_path, exc_info=True
            )

    def _save_sidecar(self) -> None:
        """Persist batch IDs to the sidecar JSON file."""
        if self._sidecar_path is None:
            return
        try:
            self._sidecar_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._sidecar_path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps({"batch_ids": self._batch_ids}, indent=2),
                encoding="utf-8",
            )
            tmp.replace(self._sidecar_path)
            logger.debug("Saved %d batch IDs to sidecar", len(self._batch_ids))
        except (OSError, TypeError):
            logger.debug(
                "Could not save sidecar file %s",
                self._sidecar_path,
                exc_info=True,
            )

    # ------------------------------------------------------------------
    # Result collection
    # ------------------------------------------------------------------

    def _collect_results(self, batch_id: str, status: Any) -> BatchResult:
        """Download results and build a :class:`BatchResult`.

        Args:
            batch_id: The completed batch ID.
            status: The batch status object from the API.

        Returns:
            A :class:`BatchResult`.

        Raises:
            BatchCancelledError: If the batch was fully cancelled.
        """
        entries: List[Dict[str, Any]] = []
        stats = BatchStats()

        # Iterate over results
        try:
            for entry in self._client.batches.results(batch_id):
                entry_dict = _entry_to_dict(entry)
                entries.append(entry_dict)

                result_type = entry_dict.get("result", {}).get("type", "")
                if result_type == "succeeded":
                    stats.succeeded += 1
                    # Record cost at 50% batch rate
                    self._record_entry_cost(entry_dict)
                elif result_type == "errored":
                    stats.failed += 1
                elif result_type == "expired":
                    stats.expired += 1
                elif result_type == "canceled":
                    stats.cancelled += 1
        except (AttributeError, KeyError, TypeError, StopIteration):
            logger.exception("Error collecting batch results for %s", batch_id)

        # Calculate total cost from usage tracker
        stats.total_cost = self._usage.estimated_cost

        result = BatchResult(entries, stats)

        # Warn on partial failure
        if stats.failed > 0 and stats.succeeded > 0:
            logger.warning(
                "Batch %s had partial failures: %d/%d failed",
                batch_id,
                stats.failed,
                stats.total,
            )

        # Raise on full cancellation
        if stats.cancelled > 0 and stats.succeeded == 0:
            raise BatchCancelledError(
                f"Batch {batch_id} was cancelled.",
                context={"batch_id": batch_id, "stats": stats.summary()},
            )

        logger.info(
            "Batch %s completed: %s", batch_id, stats.summary()
        )
        return result

    def _record_entry_cost(self, entry_dict: Dict[str, Any]) -> None:
        """Record the cost of a succeeded batch entry at 50% rate.

        Args:
            entry_dict: The entry dict with result data.
        """
        try:
            result = entry_dict.get("result", {})
            message = result.get("message", {})
            usage = message.get("usage", {})
            model = message.get("model", "")
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            cache_read = usage.get("cache_read_input_tokens", 0)
            cache_write = usage.get("cache_creation_input_tokens", 0)

            # Lazy import to avoid circular dependency
            from claudekit.client._tracked import _estimate_cost

            cost = _estimate_cost(
                model, input_tokens, output_tokens, cache_read, cache_write,
                is_batch=True,
            )

            record = CallRecord(
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_tokens=cache_read,
                cache_write_tokens=cache_write,
                estimated_cost=cost,
                is_batch=True,
            )
            self._usage.record(record)
        except (AttributeError, KeyError, TypeError, ValueError, ImportError):
            logger.debug("Could not record batch entry cost", exc_info=True)

    def __repr__(self) -> str:
        return f"BatchManager(batches={len(self._batch_ids)})"


def _entry_to_dict(entry: Any) -> Dict[str, Any]:
    """Convert a batch result entry to a plain dict.

    Handles both dict-like and object-like entries from the SDK.

    Args:
        entry: A batch result entry.

    Returns:
        A plain dict representation.
    """
    if isinstance(entry, dict):
        return entry
    # SDK objects typically have a model_dump() or to_dict() method
    if hasattr(entry, "model_dump"):
        return entry.model_dump()
    if hasattr(entry, "to_dict"):
        return entry.to_dict()
    if hasattr(entry, "__dict__"):
        return dict(entry.__dict__)
    return {"raw": str(entry)}


__all__ = ["BatchManager"]

"""Session-level usage tracking for API calls."""

from __future__ import annotations

import csv
import io
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class CallRecord:
    """Record of a single API call.

    Attributes:
        model: Model ID used for this call.
        input_tokens: Number of input tokens.
        output_tokens: Number of output tokens.
        cache_read_tokens: Tokens read from cache.
        cache_write_tokens: Tokens written to cache.
        estimated_cost: Estimated cost in USD.
        timestamp: When the call was made.
        request_id: API request ID from headers.
        idempotency_key: SDK idempotency key for dedup.
        is_batch: Whether this was a batch API call (50% discount).
        duration_ms: Call duration in milliseconds.

    Example:
        >>> record = CallRecord(model="claude-haiku-4-5", input_tokens=100, output_tokens=50)
    """

    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    estimated_cost: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    request_id: str = ""
    idempotency_key: str = ""
    is_batch: bool = False
    duration_ms: float = 0.0


class SessionUsage:
    """Thread-safe usage tracker for API calls within a session.

    Tracks tokens, costs, and call history. All properties are thread-safe.

    Attributes:
        calls: List of all recorded API calls.

    Example:
        >>> usage = SessionUsage()
        >>> usage.record(CallRecord(model="claude-haiku-4-5", input_tokens=100, output_tokens=50, estimated_cost=0.001))
        >>> print(usage.total_tokens)
        150
        >>> print(usage.estimated_cost)
        0.001
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._calls: list[CallRecord] = []
        self._seen_idempotency_keys: set[str] = set()

    def record(self, call: CallRecord) -> None:
        """Record an API call. Skips duplicate idempotency keys (retries).

        Args:
            call: The CallRecord to record.
        """
        with self._lock:
            if call.idempotency_key and call.idempotency_key in self._seen_idempotency_keys:
                return  # Skip retried request
            if call.idempotency_key:
                self._seen_idempotency_keys.add(call.idempotency_key)
            self._calls.append(call)

    @property
    def calls(self) -> list[CallRecord]:
        with self._lock:
            return list(self._calls)

    @property
    def total_tokens(self) -> int:
        with self._lock:
            return sum(c.input_tokens + c.output_tokens for c in self._calls)

    @property
    def total_input_tokens(self) -> int:
        with self._lock:
            return sum(c.input_tokens for c in self._calls)

    @property
    def total_output_tokens(self) -> int:
        with self._lock:
            return sum(c.output_tokens for c in self._calls)

    @property
    def estimated_cost(self) -> float:
        with self._lock:
            return sum(c.estimated_cost for c in self._calls)

    @property
    def total_cost(self) -> float:
        """Alias for estimated_cost."""
        return self.estimated_cost

    @property
    def call_count(self) -> int:
        with self._lock:
            return len(self._calls)

    def breakdown(self) -> dict[str, dict]:
        """Per-model cost and token breakdown.

        Returns:
            Dict mapping model ID to dict with keys: input_tokens, output_tokens, cost, call_count.
        """
        result: dict[str, dict] = {}
        with self._lock:
            for c in self._calls:
                if c.model not in result:
                    result[c.model] = {
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "cost": 0.0,
                        "call_count": 0,
                    }
                result[c.model]["input_tokens"] += c.input_tokens
                result[c.model]["output_tokens"] += c.output_tokens
                result[c.model]["cost"] += c.estimated_cost
                result[c.model]["call_count"] += 1
        return result

    def export_csv(self) -> str:
        """Export all calls as CSV string."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "timestamp", "model", "input_tokens", "output_tokens",
            "cache_read", "cache_write", "cost", "request_id", "is_batch",
        ])
        with self._lock:
            for c in self._calls:
                writer.writerow([
                    c.timestamp.isoformat(), c.model, c.input_tokens,
                    c.output_tokens, c.cache_read_tokens, c.cache_write_tokens,
                    f"{c.estimated_cost:.6f}", c.request_id, c.is_batch,
                ])
        return output.getvalue()

    def cache_savings(self) -> float:
        """Estimated savings from prompt cache hits.

        Cache read costs 10% of normal input, so savings = 90% * cache_read_tokens * price.
        """
        # We approximate using the per-call cost data
        with self._lock:
            total_savings = 0.0
            for c in self._calls:
                if c.cache_read_tokens > 0:
                    from claudekit.models import get_model

                    model = get_model(c.model)
                    if model:
                        normal_cost = c.cache_read_tokens * model.input_per_mtok / 1_000_000
                        cache_cost = c.cache_read_tokens * model.cache_read_per_mtok / 1_000_000
                        total_savings += normal_cost - cache_cost
            return total_savings

    def summary(self) -> str:
        """Human-readable usage summary."""
        lines = [
            "API Usage Summary",
            f"  Calls       : {self.call_count}",
            f"  Input tokens : {self.total_input_tokens:,}",
            f"  Output tokens: {self.total_output_tokens:,}",
            f"  Total tokens : {self.total_tokens:,}",
            f"  Est. cost    : ${self.estimated_cost:.6f}",
        ]
        savings = self.cache_savings()
        if savings > 0:
            lines.append(f"  Cache savings: ${savings:.6f}")
        bd = self.breakdown()
        if len(bd) > 1:
            lines.append("  By model:")
            for model, stats in bd.items():
                lines.append(f"    {model}: {stats['call_count']} calls, ${stats['cost']:.6f}")
        return "\n".join(lines)

    def reset(self) -> None:
        """Clear all recorded calls."""
        with self._lock:
            self._calls.clear()
            self._seen_idempotency_keys.clear()

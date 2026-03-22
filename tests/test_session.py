"""Tests for claudekit.client._session -- CallRecord and SessionUsage."""

import pytest

from claudekit.client._session import CallRecord, SessionUsage


class TestCallRecord:
    def test_defaults(self):
        record = CallRecord()
        assert record.model == ""
        assert record.input_tokens == 0
        assert record.output_tokens == 0
        assert record.cache_read_tokens == 0
        assert record.cache_write_tokens == 0
        assert record.estimated_cost == 0.0
        assert record.is_batch is False
        assert record.duration_ms == 0.0

    def test_custom_values(self):
        record = CallRecord(
            model="claude-haiku-4-5",
            input_tokens=100,
            output_tokens=50,
            estimated_cost=0.001,
        )
        assert record.model == "claude-haiku-4-5"
        assert record.input_tokens == 100
        assert record.output_tokens == 50
        assert record.estimated_cost == 0.001


class TestSessionUsage:
    def test_empty(self):
        usage = SessionUsage()
        assert usage.call_count == 0
        assert usage.total_tokens == 0
        assert usage.total_input_tokens == 0
        assert usage.total_output_tokens == 0
        assert usage.estimated_cost == 0.0
        assert usage.calls == []

    def test_record_single(self):
        usage = SessionUsage()
        usage.record(CallRecord(input_tokens=100, output_tokens=50, estimated_cost=0.001))
        assert usage.call_count == 1
        assert usage.total_tokens == 150
        assert usage.total_input_tokens == 100
        assert usage.total_output_tokens == 50
        assert usage.estimated_cost == pytest.approx(0.001)

    def test_record_multiple(self):
        usage = SessionUsage()
        usage.record(CallRecord(input_tokens=100, output_tokens=50, estimated_cost=0.001))
        usage.record(CallRecord(input_tokens=200, output_tokens=80, estimated_cost=0.003))
        assert usage.call_count == 2
        assert usage.total_tokens == 430
        assert usage.estimated_cost == pytest.approx(0.004)

    def test_idempotency_dedup(self):
        usage = SessionUsage()
        r1 = CallRecord(input_tokens=100, output_tokens=50, idempotency_key="k1")
        r2 = CallRecord(input_tokens=100, output_tokens=50, idempotency_key="k1")
        usage.record(r1)
        usage.record(r2)
        assert usage.call_count == 1

    def test_idempotency_different_keys(self):
        usage = SessionUsage()
        usage.record(CallRecord(input_tokens=10, idempotency_key="a"))
        usage.record(CallRecord(input_tokens=20, idempotency_key="b"))
        assert usage.call_count == 2

    def test_idempotency_empty_key_not_deduped(self):
        usage = SessionUsage()
        usage.record(CallRecord(input_tokens=10, idempotency_key=""))
        usage.record(CallRecord(input_tokens=20, idempotency_key=""))
        assert usage.call_count == 2

    def test_total_cost_alias(self):
        usage = SessionUsage()
        usage.record(CallRecord(estimated_cost=1.5))
        assert usage.total_cost == usage.estimated_cost

    def test_breakdown_single_model(self):
        usage = SessionUsage()
        usage.record(CallRecord(model="haiku", input_tokens=100, output_tokens=50, estimated_cost=0.01))
        bd = usage.breakdown()
        assert "haiku" in bd
        assert bd["haiku"]["call_count"] == 1
        assert bd["haiku"]["input_tokens"] == 100
        assert bd["haiku"]["output_tokens"] == 50

    def test_breakdown_multiple_models(self):
        usage = SessionUsage()
        usage.record(CallRecord(model="haiku", input_tokens=100, estimated_cost=0.01))
        usage.record(CallRecord(model="sonnet", input_tokens=200, estimated_cost=0.05))
        usage.record(CallRecord(model="haiku", input_tokens=50, estimated_cost=0.005))
        bd = usage.breakdown()
        assert bd["haiku"]["call_count"] == 2
        assert bd["sonnet"]["call_count"] == 1

    def test_export_csv(self):
        usage = SessionUsage()
        usage.record(CallRecord(model="haiku", input_tokens=100, output_tokens=50))
        csv_str = usage.export_csv()
        assert "timestamp" in csv_str
        assert "haiku" in csv_str
        lines = csv_str.strip().split("\n")
        assert len(lines) == 2  # header + 1 data row

    def test_summary_format(self):
        usage = SessionUsage()
        usage.record(CallRecord(model="haiku", input_tokens=100, output_tokens=50, estimated_cost=0.001))
        summary = usage.summary()
        assert "API Usage Summary" in summary
        assert "Calls" in summary
        assert "1" in summary

    def test_reset(self):
        usage = SessionUsage()
        usage.record(CallRecord(input_tokens=100, idempotency_key="k1"))
        usage.reset()
        assert usage.call_count == 0
        assert usage.total_tokens == 0
        # After reset, same idempotency key should be accepted
        usage.record(CallRecord(input_tokens=100, idempotency_key="k1"))
        assert usage.call_count == 1

    def test_calls_returns_copy(self):
        usage = SessionUsage()
        usage.record(CallRecord(input_tokens=10))
        calls = usage.calls
        calls.append(CallRecord(input_tokens=99))
        assert usage.call_count == 1  # original unchanged

"""Tests for claudekit.security -- SecurityLayer, Policy, SecurityContext."""

import pytest

from claudekit.security._context import SecurityContext
from claudekit.security._layer import SecurityLayer
from claudekit.security._policy import Policy


# ── Test policies ────────────────────────────────────────────────────────── #


class RecordingPolicy(Policy):
    """Policy that records all check calls."""

    name = "recording"

    def __init__(self):
        self.request_calls: list[tuple] = []
        self.response_calls: list[tuple] = []

    def check_request(self, messages, context):
        self.request_calls.append((messages, context))

    def check_response(self, response, context):
        self.response_calls.append((response, context))
        return response


class BlockingPolicy(Policy):
    """Policy that blocks all requests."""

    name = "blocker"

    def check_request(self, messages, context):
        from claudekit.errors._base import SecurityError
        raise SecurityError("Blocked by policy")


class ModifyingPolicy(Policy):
    """Policy that modifies responses."""

    name = "modifier"

    def check_response(self, response, context):
        return f"modified:{response}"


# ── SecurityContext ──────────────────────────────────────────────────────── #


class TestSecurityContext:
    def test_defaults(self):
        ctx = SecurityContext()
        assert ctx.user_id is None
        assert ctx.model == ""
        assert ctx.metadata == {}
        assert ctx.trusted_caller is False
        assert len(ctx.request_id) > 0  # auto-generated UUID

    def test_custom_values(self):
        ctx = SecurityContext(
            user_id="user-123",
            model="claude-sonnet-4-6",
            metadata={"session": "s1"},
            trusted_caller=True,
        )
        assert ctx.user_id == "user-123"
        assert ctx.model == "claude-sonnet-4-6"
        assert ctx.metadata == {"session": "s1"}
        assert ctx.trusted_caller is True

    def test_auto_request_id(self):
        ctx1 = SecurityContext()
        ctx2 = SecurityContext()
        assert ctx1.request_id != ctx2.request_id

    def test_custom_request_id(self):
        ctx = SecurityContext(request_id="custom-id")
        assert ctx.request_id == "custom-id"


# ── Policy base ──────────────────────────────────────────────────────────── #


class TestPolicy:
    def test_default_name(self):
        class MyPolicy(Policy):
            pass
        p = MyPolicy()
        assert p.name == "unnamed_policy"

    def test_check_request_noop(self):
        class MyPolicy(Policy):
            pass
        p = MyPolicy()
        ctx = SecurityContext()
        p.check_request([], ctx)  # Should not raise

    def test_check_response_passthrough(self):
        class MyPolicy(Policy):
            pass
        p = MyPolicy()
        ctx = SecurityContext()
        result = p.check_response("original", ctx)
        assert result == "original"


# ── SecurityLayer ────────────────────────────────────────────────────────── #


class TestSecurityLayer:
    def test_empty_layer_passthrough(self):
        layer = SecurityLayer()
        # Should not raise
        layer.check_request([{"role": "user", "content": "hi"}], model="m")
        result = layer.check_response("response", model="m")
        assert result == "response"

    def test_policies_run_in_order(self):
        p1 = RecordingPolicy()
        p1.name = "first"
        p2 = RecordingPolicy()
        p2.name = "second"
        layer = SecurityLayer([p1, p2])
        layer.check_request([{"role": "user", "content": "hi"}], model="m")
        assert len(p1.request_calls) == 1
        assert len(p2.request_calls) == 1

    def test_blocking_policy_raises(self):
        layer = SecurityLayer([BlockingPolicy()])
        from claudekit.errors._base import SecurityError
        with pytest.raises(SecurityError, match="Blocked"):
            layer.check_request([{"role": "user", "content": "hi"}], model="m")

    def test_response_modification(self):
        layer = SecurityLayer([ModifyingPolicy()])
        result = layer.check_response("orig", model="m")
        assert result == "modified:orig"

    def test_chained_response_modification(self):
        m1 = ModifyingPolicy()
        m1.name = "mod1"
        m2 = ModifyingPolicy()
        m2.name = "mod2"
        layer = SecurityLayer([m1, m2])
        result = layer.check_response("x", model="m")
        assert result == "modified:modified:x"


class TestSecurityLayerPolicyManagement:
    def test_add_policy(self):
        layer = SecurityLayer()
        p = RecordingPolicy()
        layer.add_policy(p)
        assert len(layer.policies) == 1
        assert layer.policies[0] is p

    def test_remove_policy(self):
        p = RecordingPolicy()
        layer = SecurityLayer([p])
        layer.remove_policy("recording")
        assert len(layer.policies) == 0

    def test_remove_nonexistent_raises(self):
        layer = SecurityLayer()
        with pytest.raises(KeyError, match="nonexistent"):
            layer.remove_policy("nonexistent")

    def test_replace_policy(self):
        p1 = RecordingPolicy()
        p2 = RecordingPolicy()
        p2.name = "recording"  # Same name
        layer = SecurityLayer([p1])
        layer.replace_policy("recording", p2)
        assert layer.policies[0] is p2

    def test_replace_nonexistent_raises(self):
        layer = SecurityLayer()
        p = RecordingPolicy()
        with pytest.raises(KeyError, match="missing"):
            layer.replace_policy("missing", p)

    def test_policies_returns_copy(self):
        p = RecordingPolicy()
        layer = SecurityLayer([p])
        policies = layer.policies
        policies.clear()
        assert len(layer.policies) == 1

    def test_repr(self):
        layer = SecurityLayer([RecordingPolicy(), BlockingPolicy()])
        r = repr(layer)
        assert "SecurityLayer" in r
        assert "recording" in r
        assert "blocker" in r

    def test_check_request_passes_context(self):
        p = RecordingPolicy()
        layer = SecurityLayer([p])
        layer.check_request(
            [{"role": "user", "content": "hi"}],
            model="claude-sonnet-4-6",
            user_id="u-1",
        )
        assert len(p.request_calls) == 1
        ctx = p.request_calls[0][1]
        assert ctx.model == "claude-sonnet-4-6"
        assert ctx.user_id == "u-1"

    def test_check_request_trusted_caller(self):
        p = RecordingPolicy()
        layer = SecurityLayer([p])
        layer.check_request(
            [{"role": "user", "content": "hi"}],
            model="m",
            trusted_caller=True,
        )
        ctx = p.request_calls[0][1]
        assert ctx.trusted_caller is True

"""Tests for claudekit.errors -- exception hierarchy and error codes."""

import pytest

from claudekit.errors._base import (
    AgentMaxTurnsError,
    AgentTimeoutError,
    BatchCancelledError,
    BatchNotReadyError,
    BatchPartialFailureError,
    BudgetExceededError,
    ClaudekitError,
    ContextWindowExceededError,
    DelegationLoopError,
    JailbreakDetectedError,
    MemoryBackendError,
    MemoryKeyNotFoundError,
    MemoryValueTooLargeError,
    OutputValidationError,
    PIIDetectedError,
    PromptInjectionError,
    RateLimitError,
    SecurityError,
    SessionBudgetExceededError,
    SessionNameConflictError,
    SessionPausedError,
    SessionTerminatedError,
    TokenLimitError,
    ToolBlockedError,
    ToolInputValidationError,
    ToolJSONError,
)
from claudekit.errors._codes import (
    BUDGET_EXCEEDED,
    PROMPT_INJECTION_DETECTED,
    TOOL_INPUT_VALIDATION_FAILED,
)


# ── ClaudekitError base ─────────────────────────────────────────────────── #


class TestClaudekitError:
    def test_defaults(self):
        err = ClaudekitError()
        assert err.message == ""
        assert err.code == ""
        assert err.context == {}
        assert err.recovery_hint is None
        assert err.original is None

    def test_with_all_fields(self):
        cause = ValueError("upstream")
        err = ClaudekitError(
            "something broke",
            code="MY_CODE",
            context={"key": "val"},
            recovery_hint="try again",
            original=cause,
        )
        assert err.message == "something broke"
        assert err.code == "MY_CODE"
        assert err.context == {"key": "val"}
        assert err.recovery_hint == "try again"
        assert err.original is cause
        assert err.__cause__ is cause

    def test_str_with_code_and_hint(self):
        err = ClaudekitError(
            "bad request", code="BR", recovery_hint="check input"
        )
        s = str(err)
        assert "bad request" in s
        assert "[BR]" in s
        assert "Hint: check input" in s

    def test_str_minimal(self):
        err = ClaudekitError("oops")
        assert str(err) == "oops"

    def test_is_exception(self):
        with pytest.raises(ClaudekitError):
            raise ClaudekitError("test")


# ── Hierarchy ────────────────────────────────────────────────────────────── #


class TestHierarchy:
    @pytest.mark.parametrize(
        "cls, base",
        [
            (SecurityError, ClaudekitError),
            (PromptInjectionError, SecurityError),
            (PIIDetectedError, SecurityError),
            (JailbreakDetectedError, SecurityError),
            (OutputValidationError, SecurityError),
            (ToolBlockedError, SecurityError),
            (BudgetExceededError, ClaudekitError),
            (RateLimitError, ClaudekitError),
            (TokenLimitError, ClaudekitError),
            (AgentTimeoutError, ClaudekitError),
            (AgentMaxTurnsError, ClaudekitError),
            (DelegationLoopError, ClaudekitError),
            (MemoryBackendError, ClaudekitError),
            (MemoryKeyNotFoundError, ClaudekitError),
            (MemoryValueTooLargeError, ClaudekitError),
            (ToolInputValidationError, ClaudekitError),
            (ToolJSONError, ClaudekitError),
            (BatchNotReadyError, ClaudekitError),
            (BatchCancelledError, ClaudekitError),
            (BatchPartialFailureError, ClaudekitError),
            (SessionPausedError, ClaudekitError),
            (SessionTerminatedError, ClaudekitError),
            (SessionNameConflictError, ClaudekitError),
            (SessionBudgetExceededError, ClaudekitError),
            (ContextWindowExceededError, ClaudekitError),
        ],
    )
    def test_subclass(self, cls, base):
        assert issubclass(cls, base)
        err = cls()
        assert isinstance(err, base)


# ── Default codes ────────────────────────────────────────────────────────── #


class TestDefaultCodes:
    def test_prompt_injection_code(self):
        assert PromptInjectionError().code == PROMPT_INJECTION_DETECTED

    def test_budget_exceeded_code(self):
        assert BudgetExceededError().code == BUDGET_EXCEEDED

    def test_tool_validation_code(self):
        assert ToolInputValidationError().code == TOOL_INPUT_VALIDATION_FAILED

    def test_security_error_has_hint(self):
        assert PromptInjectionError().recovery_hint is not None


# ── Default messages ─────────────────────────────────────────────────────── #


class TestDefaultMessages:
    @pytest.mark.parametrize(
        "cls",
        [
            PromptInjectionError,
            PIIDetectedError,
            JailbreakDetectedError,
            BudgetExceededError,
            RateLimitError,
            AgentTimeoutError,
            MemoryBackendError,
            ToolInputValidationError,
            BatchNotReadyError,
            SessionPausedError,
            ContextWindowExceededError,
        ],
    )
    def test_has_nonempty_default_message(self, cls):
        err = cls()
        assert err.message != ""

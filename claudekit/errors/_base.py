"""Base exception hierarchy for the claudekit package.

Every exception raised intentionally by claudekit is a subclass of
:class:`ClaudekitError`.  Each instance carries:

* **message** -- human-readable description of what went wrong.
* **code** -- a machine-readable constant from :mod:`claudekit.errors._codes`.
* **context** -- an arbitrary ``dict`` with structured diagnostic data.
* **recovery_hint** -- optional suggestion for the caller on how to recover.
* **original** -- the upstream exception that triggered this error, if any.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from claudekit.errors._codes import (
    AGENT_MAX_TURNS,
    AGENT_TIMEOUT,
    BATCH_CANCELLED,
    BATCH_NOT_READY,
    BATCH_PARTIAL_FAILURE,
    BUDGET_EXCEEDED,
    CONFIGURATION_ERROR,
    CONTEXT_WINDOW_EXCEEDED,
    DELEGATION_LOOP,
    DEPRECATED_MODEL,
    JAILBREAK_DETECTED,
    MEMORY_BACKEND_ERROR,
    MEMORY_KEY_NOT_FOUND,
    MEMORY_VALUE_TOO_LARGE,
    MISSING_API_KEY,
    OUTPUT_VALIDATION_FAILED,
    OVERLOADED,
    PII_DETECTED,
    PLATFORM_NOT_AVAILABLE,
    PROMPT_INJECTION_DETECTED,
    RATE_LIMIT_EXCEEDED,
    SESSION_BUDGET_EXCEEDED,
    SESSION_NAME_CONFLICT,
    SESSION_PAUSED,
    SESSION_TERMINATED,
    TOKEN_LIMIT_EXCEEDED,
    TOOL_BLOCKED,
    TOOL_INPUT_VALIDATION_FAILED,
    TOOL_JSON_ERROR,
    TOOL_RESULT_TOO_LARGE,
)


# =========================================================================== #
# Base
# =========================================================================== #
class ClaudekitError(Exception):
    """Root exception for every error raised by claudekit.

    Parameters
    ----------
    message:
        A human-readable description of the error.
    code:
        A machine-readable error code constant (see :mod:`._codes`).
    context:
        Arbitrary key/value pairs providing diagnostic detail.
    recovery_hint:
        An optional suggestion for how the caller might recover.
    original:
        The upstream exception that caused this error, if any.
    """

    def __init__(
        self,
        message: str = "",
        *,
        code: str = "",
        context: Optional[Dict[str, Any]] = None,
        recovery_hint: Optional[str] = None,
        original: Optional[BaseException] = None,
    ) -> None:
        super().__init__(message)
        self.message: str = message
        self.code: str = code
        self.context: Dict[str, Any] = context if context is not None else {}
        self.recovery_hint: Optional[str] = recovery_hint
        self.original: Optional[BaseException] = original
        if original is not None:
            self.__cause__ = original

    def __repr__(self) -> str:  # pragma: no cover
        parts = [f"{type(self).__name__}({self.message!r}"]
        if self.code:
            parts.append(f", code={self.code!r}")
        parts.append(")")
        return "".join(parts)

    def __str__(self) -> str:
        parts = [self.message]
        if self.code:
            parts.append(f" [{self.code}]")
        if self.recovery_hint:
            parts.append(f" Hint: {self.recovery_hint}")
        return "".join(parts)


# =========================================================================== #
# Security
# =========================================================================== #
class SecurityError(ClaudekitError):
    """A security policy was violated."""

    def __init__(
        self,
        message: str = "Security policy violation",
        *,
        code: str = "",
        context: Optional[Dict[str, Any]] = None,
        recovery_hint: Optional[str] = None,
        original: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            context=context,
            recovery_hint=recovery_hint,
            original=original,
        )


class PromptInjectionError(SecurityError):
    """A prompt-injection attempt was detected in user input."""

    def __init__(
        self,
        message: str = "Prompt injection detected",
        *,
        code: str = PROMPT_INJECTION_DETECTED,
        context: Optional[Dict[str, Any]] = None,
        recovery_hint: Optional[str] = "Sanitise or reject the offending input.",
        original: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            context=context,
            recovery_hint=recovery_hint,
            original=original,
        )


class PIIDetectedError(SecurityError):
    """Personally-identifiable information was found where it is prohibited."""

    def __init__(
        self,
        message: str = "PII detected in content",
        *,
        code: str = PII_DETECTED,
        context: Optional[Dict[str, Any]] = None,
        recovery_hint: Optional[str] = "Redact the PII before retrying.",
        original: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            context=context,
            recovery_hint=recovery_hint,
            original=original,
        )


class JailbreakDetectedError(SecurityError):
    """A jailbreak attempt was detected."""

    def __init__(
        self,
        message: str = "Jailbreak attempt detected",
        *,
        code: str = JAILBREAK_DETECTED,
        context: Optional[Dict[str, Any]] = None,
        recovery_hint: Optional[str] = "Reject the offending input.",
        original: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            context=context,
            recovery_hint=recovery_hint,
            original=original,
        )


class OutputValidationError(SecurityError):
    """Model output failed a post-generation validation check."""

    def __init__(
        self,
        message: str = "Output validation failed",
        *,
        code: str = OUTPUT_VALIDATION_FAILED,
        context: Optional[Dict[str, Any]] = None,
        recovery_hint: Optional[str] = "Retry with tighter system-prompt constraints.",
        original: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            context=context,
            recovery_hint=recovery_hint,
            original=original,
        )


class ToolBlockedError(SecurityError):
    """A tool invocation was blocked by a security policy."""

    def __init__(
        self,
        message: str = "Tool invocation blocked by security policy",
        *,
        code: str = TOOL_BLOCKED,
        context: Optional[Dict[str, Any]] = None,
        recovery_hint: Optional[str] = "Check the tool allow-list configuration.",
        original: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            context=context,
            recovery_hint=recovery_hint,
            original=original,
        )


# =========================================================================== #
# Budget / Rate
# =========================================================================== #
class BudgetError(ClaudekitError):
    """A budget or rate constraint was hit."""

    def __init__(
        self,
        message: str = "Budget constraint exceeded",
        *,
        code: str = "",
        context: Optional[Dict[str, Any]] = None,
        recovery_hint: Optional[str] = None,
        original: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            context=context,
            recovery_hint=recovery_hint,
            original=original,
        )


class BudgetExceededError(BudgetError):
    """The configured spend budget has been exhausted."""

    def __init__(
        self,
        message: str = "Budget exceeded",
        *,
        code: str = BUDGET_EXCEEDED,
        context: Optional[Dict[str, Any]] = None,
        recovery_hint: Optional[str] = "Increase the budget or wait for a new billing period.",
        original: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            context=context,
            recovery_hint=recovery_hint,
            original=original,
        )


class RateLimitError(BudgetError):
    """The API rate limit has been reached."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        *,
        code: str = RATE_LIMIT_EXCEEDED,
        context: Optional[Dict[str, Any]] = None,
        recovery_hint: Optional[str] = "Back off and retry after the indicated delay.",
        original: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            context=context,
            recovery_hint=recovery_hint,
            original=original,
        )


class TokenLimitError(BudgetError):
    """A per-request or per-session token limit was exceeded."""

    def __init__(
        self,
        message: str = "Token limit exceeded",
        *,
        code: str = TOKEN_LIMIT_EXCEEDED,
        context: Optional[Dict[str, Any]] = None,
        recovery_hint: Optional[str] = "Reduce the input size or raise the token cap.",
        original: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            context=context,
            recovery_hint=recovery_hint,
            original=original,
        )


# =========================================================================== #
# Agent
# =========================================================================== #
class AgentError(ClaudekitError):
    """An error arising from an agent run."""

    def __init__(
        self,
        message: str = "Agent error",
        *,
        code: str = "",
        context: Optional[Dict[str, Any]] = None,
        recovery_hint: Optional[str] = None,
        original: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            context=context,
            recovery_hint=recovery_hint,
            original=original,
        )


class AgentTimeoutError(AgentError):
    """The agent run exceeded its wall-clock timeout."""

    def __init__(
        self,
        message: str = "Agent timed out",
        *,
        code: str = AGENT_TIMEOUT,
        context: Optional[Dict[str, Any]] = None,
        recovery_hint: Optional[str] = "Increase the timeout or simplify the task.",
        original: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            context=context,
            recovery_hint=recovery_hint,
            original=original,
        )


class AgentMaxTurnsError(AgentError):
    """The agent exhausted its maximum number of turns."""

    def __init__(
        self,
        message: str = "Agent reached maximum turns",
        *,
        code: str = AGENT_MAX_TURNS,
        context: Optional[Dict[str, Any]] = None,
        recovery_hint: Optional[str] = "Increase max_turns or break the task into sub-tasks.",
        original: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            context=context,
            recovery_hint=recovery_hint,
            original=original,
        )


class DelegationLoopError(AgentError):
    """A delegation cycle was detected between sub-agents."""

    def __init__(
        self,
        message: str = "Delegation loop detected",
        *,
        code: str = DELEGATION_LOOP,
        context: Optional[Dict[str, Any]] = None,
        recovery_hint: Optional[str] = "Review delegation rules to break the cycle.",
        original: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            context=context,
            recovery_hint=recovery_hint,
            original=original,
        )


# =========================================================================== #
# Memory
# =========================================================================== #
class ClaudekitMemoryError(ClaudekitError):
    """An error in the memory subsystem.

    Named ``ClaudekitMemoryError`` to avoid shadowing the built-in
    :class:`MemoryError`.
    """

    def __init__(
        self,
        message: str = "Memory subsystem error",
        *,
        code: str = "",
        context: Optional[Dict[str, Any]] = None,
        recovery_hint: Optional[str] = None,
        original: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            context=context,
            recovery_hint=recovery_hint,
            original=original,
        )


class MemoryBackendError(ClaudekitMemoryError):
    """The memory backend (e.g. Redis, SQLite) is unreachable or returned an error."""

    def __init__(
        self,
        message: str = "Memory backend error",
        *,
        code: str = MEMORY_BACKEND_ERROR,
        context: Optional[Dict[str, Any]] = None,
        recovery_hint: Optional[str] = "Check the memory backend connection settings.",
        original: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            context=context,
            recovery_hint=recovery_hint,
            original=original,
        )


class MemoryKeyNotFoundError(ClaudekitMemoryError):
    """The requested key does not exist in the memory store."""

    def __init__(
        self,
        message: str = "Memory key not found",
        *,
        code: str = MEMORY_KEY_NOT_FOUND,
        context: Optional[Dict[str, Any]] = None,
        recovery_hint: Optional[str] = "Verify the key name or populate it before reading.",
        original: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            context=context,
            recovery_hint=recovery_hint,
            original=original,
        )


class MemoryValueTooLargeError(ClaudekitMemoryError):
    """The value exceeds the configured maximum size for memory entries."""

    def __init__(
        self,
        message: str = "Memory value too large",
        *,
        code: str = MEMORY_VALUE_TOO_LARGE,
        context: Optional[Dict[str, Any]] = None,
        recovery_hint: Optional[str] = "Reduce the value size or increase the limit.",
        original: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            context=context,
            recovery_hint=recovery_hint,
            original=original,
        )


# =========================================================================== #
# Tool
# =========================================================================== #
class ToolInputValidationError(ClaudekitError):
    """The model-supplied input for a tool failed schema validation."""

    def __init__(
        self,
        message: str = "Tool input validation failed",
        *,
        code: str = TOOL_INPUT_VALIDATION_FAILED,
        context: Optional[Dict[str, Any]] = None,
        recovery_hint: Optional[str] = "Check the tool schema and retry.",
        original: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            context=context,
            recovery_hint=recovery_hint,
            original=original,
        )


class ToolResultTooLargeWarning(UserWarning):
    """Warning emitted when a tool result is larger than recommended.

    This is a :class:`UserWarning`, **not** an exception, so it can be
    filtered with the standard :mod:`warnings` module.
    """


class ToolJSONError(ClaudekitError):
    """A tool returned non-JSON or malformed JSON when JSON was expected."""

    def __init__(
        self,
        message: str = "Tool JSON error",
        *,
        code: str = TOOL_JSON_ERROR,
        context: Optional[Dict[str, Any]] = None,
        recovery_hint: Optional[str] = "Ensure the tool returns valid JSON.",
        original: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            context=context,
            recovery_hint=recovery_hint,
            original=original,
        )


# =========================================================================== #
# Batch
# =========================================================================== #
class BatchError(ClaudekitError):
    """An error in the batch-processing subsystem."""

    def __init__(
        self,
        message: str = "Batch error",
        *,
        code: str = "",
        context: Optional[Dict[str, Any]] = None,
        recovery_hint: Optional[str] = None,
        original: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            context=context,
            recovery_hint=recovery_hint,
            original=original,
        )


class BatchNotReadyError(BatchError):
    """The batch result was requested before processing completed."""

    def __init__(
        self,
        message: str = "Batch not ready",
        *,
        code: str = BATCH_NOT_READY,
        context: Optional[Dict[str, Any]] = None,
        recovery_hint: Optional[str] = "Poll the batch status or use an async callback.",
        original: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            context=context,
            recovery_hint=recovery_hint,
            original=original,
        )


class BatchCancelledError(BatchError):
    """The batch was cancelled before it completed."""

    def __init__(
        self,
        message: str = "Batch cancelled",
        *,
        code: str = BATCH_CANCELLED,
        context: Optional[Dict[str, Any]] = None,
        recovery_hint: Optional[str] = "Re-submit the batch if cancellation was unintended.",
        original: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            context=context,
            recovery_hint=recovery_hint,
            original=original,
        )


class BatchPartialFailureError(BatchError):
    """Some items in the batch failed while others succeeded."""

    def __init__(
        self,
        message: str = "Batch partial failure",
        *,
        code: str = BATCH_PARTIAL_FAILURE,
        context: Optional[Dict[str, Any]] = None,
        recovery_hint: Optional[str] = "Inspect context['failed_items'] and retry them.",
        original: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            context=context,
            recovery_hint=recovery_hint,
            original=original,
        )


# =========================================================================== #
# Session
# =========================================================================== #
class SessionError(ClaudekitError):
    """An error in the session-management subsystem."""

    def __init__(
        self,
        message: str = "Session error",
        *,
        code: str = "",
        context: Optional[Dict[str, Any]] = None,
        recovery_hint: Optional[str] = None,
        original: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            context=context,
            recovery_hint=recovery_hint,
            original=original,
        )


class SessionPausedError(SessionError):
    """An operation was attempted on a paused session."""

    def __init__(
        self,
        message: str = "Session is paused",
        *,
        code: str = SESSION_PAUSED,
        context: Optional[Dict[str, Any]] = None,
        recovery_hint: Optional[str] = "Resume the session before performing operations.",
        original: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            context=context,
            recovery_hint=recovery_hint,
            original=original,
        )


class SessionTerminatedError(SessionError):
    """An operation was attempted on a terminated session."""

    def __init__(
        self,
        message: str = "Session is terminated",
        *,
        code: str = SESSION_TERMINATED,
        context: Optional[Dict[str, Any]] = None,
        recovery_hint: Optional[str] = "Create a new session.",
        original: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            context=context,
            recovery_hint=recovery_hint,
            original=original,
        )


class SessionNameConflictError(SessionError):
    """A session with the same name already exists."""

    def __init__(
        self,
        message: str = "Session name conflict",
        *,
        code: str = SESSION_NAME_CONFLICT,
        context: Optional[Dict[str, Any]] = None,
        recovery_hint: Optional[str] = "Use a unique session name or resume the existing one.",
        original: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            context=context,
            recovery_hint=recovery_hint,
            original=original,
        )


class SessionBudgetExceededError(SessionError):
    """The per-session budget has been exhausted."""

    def __init__(
        self,
        message: str = "Session budget exceeded",
        *,
        code: str = SESSION_BUDGET_EXCEEDED,
        context: Optional[Dict[str, Any]] = None,
        recovery_hint: Optional[str] = "Increase the session budget or start a new session.",
        original: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            context=context,
            recovery_hint=recovery_hint,
            original=original,
        )


# =========================================================================== #
# Precheck
# =========================================================================== #
class PrecheckError(ClaudekitError):
    """A pre-flight check failed before the request was sent."""

    def __init__(
        self,
        message: str = "Precheck failed",
        *,
        code: str = "",
        context: Optional[Dict[str, Any]] = None,
        recovery_hint: Optional[str] = None,
        original: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            context=context,
            recovery_hint=recovery_hint,
            original=original,
        )


class ContextWindowExceededError(PrecheckError):
    """The estimated token count exceeds the model's context window."""

    def __init__(
        self,
        message: str = "Context window exceeded",
        *,
        code: str = CONTEXT_WINDOW_EXCEEDED,
        context: Optional[Dict[str, Any]] = None,
        recovery_hint: Optional[str] = "Reduce the input size or use a model with a larger context window.",
        original: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            context=context,
            recovery_hint=recovery_hint,
            original=original,
        )


# =========================================================================== #
# Orchestrator
# =========================================================================== #
class OrchestratorError(ClaudekitError):
    """An error originating from the orchestration layer."""

    def __init__(
        self,
        message: str = "Orchestrator error",
        *,
        code: str = "",
        context: Optional[Dict[str, Any]] = None,
        recovery_hint: Optional[str] = None,
        original: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            context=context,
            recovery_hint=recovery_hint,
            original=original,
        )


# =========================================================================== #
# Configuration
# =========================================================================== #
class ConfigurationError(ClaudekitError):
    """A configuration or environment problem prevents normal operation."""

    def __init__(
        self,
        message: str = "Configuration error",
        *,
        code: str = CONFIGURATION_ERROR,
        context: Optional[Dict[str, Any]] = None,
        recovery_hint: Optional[str] = None,
        original: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            context=context,
            recovery_hint=recovery_hint,
            original=original,
        )


class MissingAPIKeyError(ConfigurationError):
    """No API key was provided or the provided key is invalid."""

    def __init__(
        self,
        message: str = "Missing or invalid API key",
        *,
        code: str = MISSING_API_KEY,
        context: Optional[Dict[str, Any]] = None,
        recovery_hint: Optional[str] = "Set the ANTHROPIC_API_KEY environment variable or pass api_key explicitly.",
        original: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            context=context,
            recovery_hint=recovery_hint,
            original=original,
        )


class DeprecatedModelError(ConfigurationError):
    """The requested model has been deprecated and is no longer available."""

    def __init__(
        self,
        message: str = "Model is deprecated",
        *,
        code: str = DEPRECATED_MODEL,
        context: Optional[Dict[str, Any]] = None,
        recovery_hint: Optional[str] = "Switch to a supported model.",
        original: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            context=context,
            recovery_hint=recovery_hint,
            original=original,
        )


class PlatformNotAvailableError(ConfigurationError):
    """The requested platform or feature is not available in this environment."""

    def __init__(
        self,
        message: str = "Platform not available",
        *,
        code: str = PLATFORM_NOT_AVAILABLE,
        context: Optional[Dict[str, Any]] = None,
        recovery_hint: Optional[str] = "Check platform requirements and supported environments.",
        original: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            context=context,
            recovery_hint=recovery_hint,
            original=original,
        )


# =========================================================================== #
# SDK wrapper: Overloaded
# =========================================================================== #
class OverloadedError(ClaudekitError):
    """The Anthropic API is temporarily overloaded (HTTP 529)."""

    def __init__(
        self,
        message: str = "API is overloaded",
        *,
        code: str = OVERLOADED,
        context: Optional[Dict[str, Any]] = None,
        recovery_hint: Optional[str] = "Retry with exponential back-off.",
        original: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            context=context,
            recovery_hint=recovery_hint,
            original=original,
        )

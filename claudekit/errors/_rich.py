"""Rich error wrapping for the Anthropic Python SDK.

Calling :func:`enable_rich_errors` monkey-patches :func:`sys.excepthook` so
that unhandled ``anthropic`` SDK exceptions are automatically wrapped in the
richer :class:`~claudekit.errors.ClaudekitError` hierarchy before being
displayed.  This gives callers structured error codes, recovery hints, and
preserved original exceptions for every failure mode.

Also exports :class:`DeprecatedModelWarning`, a :class:`UserWarning` subclass
used to signal that a model identifier is deprecated but still functional.
"""

from __future__ import annotations

import logging
import sys
import types
from typing import Any, Dict, Optional, Type

from claudekit.errors._base import (
    AgentTimeoutError,
    ClaudekitError,
    ConfigurationError,
    ContextWindowExceededError,
    MissingAPIKeyError,
    OverloadedError,
    RateLimitError,
)
from claudekit.errors._codes import (
    API_CONNECTION_ERROR,
    API_TIMEOUT,
    CONTEXT_WINDOW_EXCEEDED,
    MISSING_API_KEY,
    OVERLOADED,
    RATE_LIMIT_EXCEEDED,
)

logger = logging.getLogger("claudekit.errors")

# ---------------------------------------------------------------------------
# DeprecatedModelWarning
# ---------------------------------------------------------------------------


class DeprecatedModelWarning(UserWarning):
    """Warning emitted when a deprecated (but still functional) model is used.

    This is a :class:`UserWarning`, not an exception.  It can be silenced
    via the standard :mod:`warnings` filter mechanism::

        import warnings
        from claudekit.errors import DeprecatedModelWarning
        warnings.filterwarnings("ignore", category=DeprecatedModelWarning)
    """


# ---------------------------------------------------------------------------
# Internal: SDK exception → claudekit exception mapping
# ---------------------------------------------------------------------------

def _extract_request_id(exc: BaseException) -> Optional[str]:
    """Try to pull the ``x-request-id`` header from an anthropic error response."""
    # anthropic SDK errors store the response on the exception when available.
    response = getattr(exc, "response", None)
    if response is not None:
        headers = getattr(response, "headers", None)
        if headers is not None:
            return headers.get("x-request-id") or headers.get("request-id")
    return None


def _extract_status_code(exc: BaseException) -> Optional[int]:
    """Try to pull the HTTP status code from an anthropic error."""
    status = getattr(exc, "status_code", None)
    if status is not None:
        return int(status)
    response = getattr(exc, "response", None)
    if response is not None:
        resp_status = getattr(response, "status_code", None)
        if resp_status is not None:
            return int(resp_status)
    return None


def _build_context(exc: BaseException) -> Dict[str, Any]:
    """Build a diagnostic context dict from an SDK exception."""
    ctx: Dict[str, Any] = {}
    status = _extract_status_code(exc)
    if status is not None:
        ctx["status_code"] = status
    request_id = _extract_request_id(exc)
    if request_id is not None:
        ctx["request_id"] = request_id
    body = getattr(exc, "body", None)
    if body is not None:
        ctx["body"] = body
    return ctx


def _wrap_sdk_exception(exc: BaseException) -> Optional[ClaudekitError]:
    """Attempt to wrap an anthropic SDK exception in a claudekit error.

    Returns ``None`` if the exception is not a recognised anthropic SDK type.
    """
    try:
        import anthropic  # noqa: F811 — lazy import so anthropic is optional
    except ImportError:
        return None

    ctx = _build_context(exc)
    msg = str(exc)

    # --- Connection / Timeout (no HTTP status) ---
    if isinstance(exc, anthropic.APIConnectionError):
        return ConfigurationError(
            message=msg,
            code=API_CONNECTION_ERROR,
            context=ctx,
            recovery_hint="Check your network connection and proxy settings.",
            original=exc,
        )

    if isinstance(exc, anthropic.APITimeoutError):
        return AgentTimeoutError(
            message=msg,
            code=API_TIMEOUT,
            context=ctx,
            recovery_hint="Increase the client timeout or retry.",
            original=exc,
        )

    # --- Status-code based errors ---
    # Order matters: check subclasses before their parents where the SDK
    # defines a hierarchy (e.g. OverloadedError < InternalServerError).

    if isinstance(exc, anthropic.AuthenticationError):  # 401
        return MissingAPIKeyError(
            message=msg,
            code=MISSING_API_KEY,
            context=ctx,
            recovery_hint="Set the ANTHROPIC_API_KEY environment variable or pass api_key explicitly.",
            original=exc,
        )

    if isinstance(exc, anthropic.PermissionDeniedError):  # 403
        return ConfigurationError(
            message=msg,
            code=API_CONNECTION_ERROR,
            context=ctx,
            recovery_hint="Verify your API key has the required permissions.",
            original=exc,
        )

    if isinstance(exc, anthropic.RateLimitError):  # 429
        return RateLimitError(
            message=msg,
            code=RATE_LIMIT_EXCEEDED,
            context=ctx,
            recovery_hint="Back off and retry after the indicated delay.",
            original=exc,
        )

    # RequestTooLarge (413) — map to context-window exceeded
    _request_too_large = getattr(anthropic, "RequestTooLargeError", None)
    if _request_too_large is not None and isinstance(exc, _request_too_large):
        return ContextWindowExceededError(
            message=msg,
            code=CONTEXT_WINDOW_EXCEEDED,
            context=ctx,
            recovery_hint="Reduce the input size or use a model with a larger context window.",
            original=exc,
        )

    # OverloadedError (529) — must be checked before InternalServerError
    _overloaded = getattr(anthropic, "OverloadedError", None)
    if _overloaded is not None and isinstance(exc, _overloaded):
        return OverloadedError(
            message=msg,
            code=OVERLOADED,
            context=ctx,
            recovery_hint="Retry with exponential back-off.",
            original=exc,
        )

    # ServiceUnavailableError (503)
    _service_unavailable = getattr(anthropic, "ServiceUnavailableError", None)
    if _service_unavailable is not None and isinstance(exc, _service_unavailable):
        return ClaudekitError(
            message=msg,
            code=API_CONNECTION_ERROR,
            context=ctx,
            recovery_hint="The API is temporarily unavailable. Retry shortly.",
            original=exc,
        )

    # InternalServerError (500+) — catch-all for server errors
    if isinstance(exc, anthropic.InternalServerError):
        return ClaudekitError(
            message=msg,
            code=API_CONNECTION_ERROR,
            context=ctx,
            recovery_hint="An internal server error occurred. Retry or contact support.",
            original=exc,
        )

    # UnprocessableEntityError (422)
    _unprocessable = getattr(anthropic, "UnprocessableEntityError", None)
    if _unprocessable is not None and isinstance(exc, _unprocessable):
        return ClaudekitError(
            message=msg,
            code="UNPROCESSABLE_ENTITY",
            context=ctx,
            recovery_hint="Check the request payload for semantic errors.",
            original=exc,
        )

    # ConflictError (409)
    _conflict = getattr(anthropic, "ConflictError", None)
    if _conflict is not None and isinstance(exc, _conflict):
        return ClaudekitError(
            message=msg,
            code="CONFLICT",
            context=ctx,
            recovery_hint="The request conflicts with server state. Retry with updated data.",
            original=exc,
        )

    # NotFoundError (404)
    if isinstance(exc, anthropic.NotFoundError):
        return ClaudekitError(
            message=msg,
            code="NOT_FOUND",
            context=ctx,
            recovery_hint="Check the resource identifier.",
            original=exc,
        )

    # BadRequestError (400) — generic catch-all
    if isinstance(exc, anthropic.BadRequestError):
        return ClaudekitError(
            message=msg,
            code="BAD_REQUEST",
            context=ctx,
            recovery_hint="Check the request parameters.",
            original=exc,
        )

    # Catch-all for any remaining anthropic.APIError subclass
    if isinstance(exc, anthropic.APIError):
        return ClaudekitError(
            message=msg,
            context=ctx,
            recovery_hint="An unexpected API error occurred.",
            original=exc,
        )

    return None


# ---------------------------------------------------------------------------
# Public: enable_rich_errors
# ---------------------------------------------------------------------------

_original_excepthook: Optional[Any] = None


def _rich_excepthook(
    exc_type: Type[BaseException],
    exc_value: BaseException,
    exc_tb: types.TracebackType | None,
) -> None:
    """Custom :func:`sys.excepthook` that wraps anthropic errors.

    If the exception is a recognised anthropic SDK error, it is wrapped in
    the corresponding claudekit error and displayed.  Otherwise the original
    hook is called unchanged.
    """
    wrapped = _wrap_sdk_exception(exc_value)
    if wrapped is not None:
        logger.debug(
            "Wrapped %s in %s",
            type(exc_value).__name__,
            type(wrapped).__name__,
        )
        # Display the wrapped error using the original hook so that normal
        # traceback formatting is preserved.
        if _original_excepthook is not None:
            _original_excepthook(type(wrapped), wrapped, exc_tb)
        else:
            sys.__excepthook__(type(wrapped), wrapped, exc_tb)
    else:
        if _original_excepthook is not None:
            _original_excepthook(exc_type, exc_value, exc_tb)
        else:
            sys.__excepthook__(exc_type, exc_value, exc_tb)


def enable_rich_errors() -> None:
    """Patch :func:`sys.excepthook` to wrap anthropic SDK errors.

    Calling this function more than once is safe; the original hook is only
    saved on the first invocation.

    Example::

        from claudekit.errors import enable_rich_errors
        enable_rich_errors()

        # From this point, any unhandled anthropic.RateLimitError will surface
        # as claudekit.errors.RateLimitError with structured context.
    """
    global _original_excepthook  # noqa: PLW0603

    if sys.excepthook is _rich_excepthook:
        # Already patched — nothing to do.
        return

    _original_excepthook = sys.excepthook
    sys.excepthook = _rich_excepthook
    logger.debug("claudekit rich error hook installed")


def wrap_sdk_error(exc: BaseException) -> ClaudekitError:
    """Programmatically wrap an anthropic SDK exception.

    Unlike :func:`enable_rich_errors` (which patches the global except-hook),
    this helper can be used inside ``try``/``except`` blocks to convert a
    caught SDK error on demand::

        import anthropic
        from claudekit.errors import wrap_sdk_error

        try:
            client.messages.create(...)
        except anthropic.APIError as exc:
            raise wrap_sdk_error(exc) from exc

    If *exc* is not a recognised anthropic exception, a generic
    :class:`ClaudekitError` is returned.
    """
    wrapped = _wrap_sdk_exception(exc)
    if wrapped is not None:
        return wrapped
    return ClaudekitError(
        message=str(exc),
        context=_build_context(exc),
        recovery_hint="An unexpected error occurred.",
        original=exc,
    )

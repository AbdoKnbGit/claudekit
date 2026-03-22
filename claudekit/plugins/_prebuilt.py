"""Pre-built plugins shipped with claudekit.

Provides:
- :class:`LoggingPlugin` -- structured logging for all lifecycle events
- :class:`CostAlertPlugin` -- fires a callback when cost exceeds a threshold
- :class:`OpenTelemetryPlugin` -- creates OpenTelemetry tracing spans (no-op if otel not installed)
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from claudekit.plugins._plugin import Plugin

logger = logging.getLogger(__name__)


class LoggingPlugin(Plugin):
    """Logs all requests, responses, tool calls, and costs.

    Parameters
    ----------
    logger_instance:
        Custom logger. Defaults to ``logging.getLogger("claudekit.plugin.logging")``.
    level:
        Logging level. Defaults to ``"INFO"``.
    include_content:
        If ``True``, log message and response content. Defaults to ``False``
        to avoid logging sensitive data.

    Example
    -------
    ::

        from claudekit.plugins import LoggingPlugin

        plugin = LoggingPlugin(include_content=False)
    """

    name: str = "logging"
    version: str = "1.0.0"

    def __init__(
        self,
        logger_instance: Optional[logging.Logger] = None,
        level: str = "INFO",
        include_content: bool = False,
    ) -> None:
        self._logger = logger_instance or logging.getLogger("claudekit.plugin.logging")
        self._level = getattr(logging, level.upper(), logging.INFO)
        self._include_content = include_content

    def on_request(self, messages: list[dict[str, Any]], model: str, context: Any = None) -> None:
        msg = f"Request: model={model}, messages={len(messages)}"
        if self._include_content and messages:
            last = messages[-1].get("content", "")
            if isinstance(last, str):
                msg += f", content={last[:100]!r}"
        self._logger.log(self._level, msg)

    def on_response(self, response: Any, context: Any = None) -> Any:
        model = getattr(response, "model", "unknown")
        usage = getattr(response, "usage", None)
        tokens = ""
        if usage:
            tokens = f", in={getattr(usage, 'input_tokens', 0)}, out={getattr(usage, 'output_tokens', 0)}"
        self._logger.log(self._level, "Response: model=%s%s", model, tokens)
        return response

    def on_tool_call(self, tool_name: str, tool_input: dict[str, Any], context: Any = None) -> None:
        self._logger.log(self._level, "Tool call: %s", tool_name)

    def on_tool_result(self, tool_name: str, result: Any, context: Any = None) -> None:
        self._logger.log(self._level, "Tool result: %s", tool_name)

    def on_session_start(self, session_name: str, config: Any = None) -> None:
        self._logger.log(self._level, "Session started: %s", session_name)

    def on_session_cost_update(self, session_name: str, cost_usd: float, usage: Any = None) -> None:
        self._logger.log(self._level, "Session %s cost: $%.4f", session_name, cost_usd)

    def on_session_end(self, session_name: str, usage: Any = None) -> None:
        self._logger.log(self._level, "Session ended: %s", session_name)

    def on_error(self, error: Exception, context: Any = None) -> None:
        self._logger.error("Error: %s: %s", type(error).__name__, error)

    def on_security_event(self, event_type: str, details: dict[str, Any], context: Any = None) -> None:
        self._logger.log(self._level, "Security event: %s %s", event_type, details)


class CostAlertPlugin(Plugin):
    """Fires a callback when cumulative cost exceeds a threshold.

    Parameters
    ----------
    threshold_usd:
        Cost threshold in USD.
    callback:
        Function called with (cost_usd, session_name) when the threshold is reached.
    per_session:
        If ``True``, track thresholds per session. If ``False``, track globally.

    Example
    -------
    ::

        from claudekit.plugins import CostAlertPlugin

        def alert(cost, session):
            print(f"Cost alert: ${cost:.2f} in {session}")

        plugin = CostAlertPlugin(threshold_usd=1.00, callback=alert)
    """

    name: str = "cost_alert"
    version: str = "1.0.0"

    def __init__(
        self,
        threshold_usd: float = 1.00,
        callback: Optional[Callable[..., None]] = None,
        per_session: bool = False,
    ) -> None:
        self._threshold = threshold_usd
        self._callback = callback or (lambda cost, session: None)
        self._per_session = per_session
        self._global_cost = 0.0
        self._session_costs: dict[str, float] = {}
        self._alerted_global = False
        self._alerted_sessions: set[str] = set()

    def on_session_cost_update(self, session_name: str, cost_usd: float, usage: Any = None) -> None:
        if self._per_session:
            self._session_costs[session_name] = cost_usd
            if cost_usd >= self._threshold and session_name not in self._alerted_sessions:
                self._alerted_sessions.add(session_name)
                logger.warning(
                    "CostAlertPlugin: session %s exceeded $%.2f (current: $%.4f)",
                    session_name, self._threshold, cost_usd,
                )
                try:
                    self._callback(cost_usd, session_name)
                except (TypeError, ValueError, RuntimeError):
                    logger.exception("CostAlertPlugin callback failed")
        else:
            self._global_cost += cost_usd
            if self._global_cost >= self._threshold and not self._alerted_global:
                self._alerted_global = True
                logger.warning(
                    "CostAlertPlugin: global cost exceeded $%.2f (current: $%.4f)",
                    self._threshold, self._global_cost,
                )
                try:
                    self._callback(self._global_cost, session_name)
                except (TypeError, ValueError, RuntimeError):
                    logger.exception("CostAlertPlugin callback failed")


class OpenTelemetryPlugin(Plugin):
    """Creates OpenTelemetry spans for API calls, tool calls, and sessions.

    No-op if ``opentelemetry`` is not installed — never raises ImportError.

    Parameters
    ----------
    tracer:
        Custom OpenTelemetry tracer. If ``None``, creates one from the global
        tracer provider using *service_name*.
    service_name:
        Service name for the tracer. Defaults to ``"claudekit"``.

    Example
    -------
    ::

        from claudekit.plugins import OpenTelemetryPlugin

        plugin = OpenTelemetryPlugin(service_name="my-app")
    """

    name: str = "opentelemetry"
    version: str = "1.0.0"

    def __init__(
        self,
        tracer: Any = None,
        service_name: str = "claudekit",
    ) -> None:
        self._tracer = tracer
        self._service_name = service_name
        self._otel_available = False

        if tracer is None:
            try:
                from opentelemetry import trace
                self._tracer = trace.get_tracer(service_name)
                self._otel_available = True
            except ImportError:
                self._otel_available = False
                logger.debug("OpenTelemetry not installed; OpenTelemetryPlugin is a no-op")
        else:
            self._otel_available = True

    def on_request(self, messages: list[dict[str, Any]], model: str, context: Any = None) -> None:
        if not self._otel_available or self._tracer is None:
            return
        try:
            span = self._tracer.start_span(f"claude.request.{model}")
            span.set_attribute("claude.model", model)
            span.set_attribute("claude.message_count", len(messages))
            span.end()
        except (AttributeError, RuntimeError):
            logger.debug("OpenTelemetryPlugin: failed to create request span", exc_info=True)

    def on_tool_call(self, tool_name: str, tool_input: dict[str, Any], context: Any = None) -> None:
        if not self._otel_available or self._tracer is None:
            return
        try:
            span = self._tracer.start_span(f"claude.tool.{tool_name}")
            span.set_attribute("claude.tool_name", tool_name)
            span.end()
        except (AttributeError, RuntimeError):
            logger.debug("OpenTelemetryPlugin: failed to create tool span", exc_info=True)

    def on_session_start(self, session_name: str, config: Any = None) -> None:
        if not self._otel_available or self._tracer is None:
            return
        try:
            span = self._tracer.start_span(f"claude.session.{session_name}")
            span.set_attribute("claude.session_name", session_name)
            span.end()
        except (AttributeError, RuntimeError):
            logger.debug("OpenTelemetryPlugin: failed to create session span", exc_info=True)


__all__ = ["CostAlertPlugin", "LoggingPlugin", "OpenTelemetryPlugin"]

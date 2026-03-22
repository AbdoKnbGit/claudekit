"""AgentRunner -- execute an :class:`~claudekit.agents.Agent` via the Claude Agent SDK.

The runner is the bridge between claudekit's declarative :class:`Agent` dataclass
and the imperative ``claude_agent_sdk.query()`` call.  It handles SDK import,
argument mapping, timeout enforcement, and result packaging.

SDK contract (claude-agent-sdk):
    query(*, prompt, options: ClaudeAgentOptions) -> AsyncIterator[Message]

    ClaudeAgentOptions accepted fields (verified against SDK):
        model, system_prompt, max_turns, allowed_tools, disallowed_tools,
        permission_mode, effort, max_budget_usd, hooks (dict), resume,
        tools, cwd, env, fallback_model, user, ...

    NOT accepted by ClaudeAgentOptions:
        context       -- inject values directly into the prompt string
        max_cost_usd  -- use max_budget_usd instead
        session_id    -- use resume instead

    Message types yielded by query():
        SystemMessage      -- init info
        AssistantMessage   -- model response (content: list[TextBlock | ThinkingBlock])
        ResultMessage      -- final summary (total_cost_usd, num_turns, session_id)

    ResultMessage fields:
        subtype, duration_ms, duration_api_ms, is_error, num_turns,
        session_id, stop_reason, total_cost_usd, usage, result,
        structured_output
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, Optional

logger = logging.getLogger(__name__)


# =========================================================================== #
# Result
# =========================================================================== #
@dataclass
class AgentResult:
    """The outcome of a single agent run.

    Attributes
    ----------
    output:
        The agent's final textual response.
    turns:
        Number of conversational turns consumed.
    total_tokens:
        Always 0 — the subprocess SDK does not report token counts.
        Use TrackedClient for token tracking.
    total_cost:
        Always 0.0 — the subprocess SDK does not report cost.
        Use TrackedClient for cost tracking.
    duration_seconds:
        Wall-clock time elapsed during execution.
    messages:
        Raw list of messages exchanged (as strings).
    session_id:
        Session identifier from the SDK ResultMessage, if available.
    """

    output: str = ""
    turns: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    duration_seconds: float = 0.0
    messages: list[Any] = field(default_factory=list)
    session_id: Optional[str] = None

    def __repr__(self) -> str:
        return (
            f"AgentResult(output={self.output[:80]!r}..., turns={self.turns}, "
            f"total_tokens={self.total_tokens}, total_cost=${self.total_cost:.4f}, "
            f"duration_seconds={self.duration_seconds:.2f})"
        )


# =========================================================================== #
# Runner
# =========================================================================== #
class AgentRunner:
    """Execute an :class:`~claudekit.agents.Agent` against the Claude Agent SDK.

    Parameters
    ----------
    agent:
        The :class:`~claudekit.agents.Agent` definition to run.
    hooks:
        Optional hook dict in the SDK's expected format:
        ``{event_name: [callable, ...], ...}``

        .. warning::
            :class:`~claudekit.agents.HookBuilder` produces a **list** format
            that is incompatible with the agent SDK subprocess.  Use HookBuilder
            hooks only with ``TrackedClient.messages.create()``.

    sdk_kwargs:
        Extra keyword arguments merged into ClaudeAgentOptions.

    Examples
    --------
    >>> agent = Agent(name="helper", model="claude-haiku-4-5-20251001",
    ...               system="Be helpful.", effort="low", max_turns=3)
    >>> runner = AgentRunner(agent)
    >>> result = runner.run("What is 2 + 2?")
    >>> print(result.output)
    """

    def __init__(
        self,
        agent: Any,
        *,
        hooks: Optional[dict[str, Any]] = None,
        sdk_kwargs: Optional[dict[str, Any]] = None,
        direct: bool = False,
        client: Optional[Any] = None,
    ) -> None:
        self._agent = agent
        self._direct = direct
        self._direct_client = client

        if isinstance(hooks, list):
            logger.warning(
                "AgentRunner: hooks must be a dict for the agent SDK "
                "({'PreToolUse': [fn]}). HookBuilder produces a list format — "
                "use HookBuilder with TrackedClient instead. Ignoring hooks."
            )
            self._hooks: Optional[dict[str, Any]] = None
        else:
            self._hooks = hooks

        self._sdk_kwargs: dict[str, Any] = sdk_kwargs or {}
        self._sdk: Any = None

        logger.debug(
            "AgentRunner initialised for agent '%s' (model=%s, effort=%s, direct=%s)",
            agent.name, agent.model, agent.effort, direct,
        )

    # ------------------------------------------------------------------ #
    # SDK import
    # ------------------------------------------------------------------ #
    def _ensure_sdk(self) -> Any:
        """Lazily import and cache ``claude_agent_sdk``."""
        if self._sdk is not None:
            return self._sdk
        try:
            import claude_agent_sdk  # type: ignore[import-untyped]
            self._sdk = claude_agent_sdk
            logger.debug("claude_agent_sdk loaded")
            return self._sdk
        except ImportError as exc:
            from claudekit.errors import ConfigurationError
            raise ConfigurationError(
                "claude_agent_sdk is not installed",
                code="CONFIGURATION_ERROR",
                context={"package": "claude_agent_sdk"},
                recovery_hint="pip install claude-agent-sdk",
                original=exc,
            ) from exc

    # ------------------------------------------------------------------ #
    # Build ClaudeAgentOptions
    # ------------------------------------------------------------------ #
    def _build_query_kwargs(
        self,
        prompt: str,
        session_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Map Agent fields → ClaudeAgentOptions and return query kwargs dict.

        Only fields accepted by ClaudeAgentOptions are included.
        Unsupported fields (context, ToolWrapper objects) are silently dropped
        with a debug log.
        """
        from claude_agent_sdk import ClaudeAgentOptions  # type: ignore[import-untyped]

        agent = self._agent
        opts: dict[str, Any] = {}

        if agent.model:
            opts["model"] = agent.model

        if agent.system:
            opts["system_prompt"] = agent.system

        # allowed_tools / disallowed_tools must be list[str]
        if agent.allowed_tools is not None:
            opts["allowed_tools"] = [str(t) for t in agent.allowed_tools]

        if agent.disallowed_tools is not None:
            opts["disallowed_tools"] = [str(t) for t in agent.disallowed_tools]

        if agent.permission_mode and agent.permission_mode != "default":
            opts["permission_mode"] = agent.permission_mode

        if agent.max_turns is not None:
            opts["max_turns"] = agent.max_turns

        if agent.max_cost_usd is not None:
            opts["max_budget_usd"] = agent.max_cost_usd

        if agent.effort and agent.effort != "medium":
            opts["effort"] = agent.effort

        # hooks must be dict: {event_name: [callable, ...]}
        if self._hooks is not None:
            opts["hooks"] = self._hooks

        if session_id is not None:
            opts["resume"] = session_id

        # agent.tools (ToolWrapper objects) are NOT passed —
        # the subprocess CLI cannot load Python callables.
        if agent.tools:
            logger.debug(
                "AgentRunner: agent.tools contains Python callables which the "
                "subprocess SDK cannot use. Ignoring. Use TrackedClient for "
                "custom @tool functions, or add tool names to allowed_tools."
            )

        # agent.context dict is NOT passed — not a ClaudeAgentOptions field.
        # Callers should format context values into the prompt string directly.

        opts.update(self._sdk_kwargs)

        # Build options — fall back to safe subset if an unexpected field slips through
        try:
            options = ClaudeAgentOptions(**opts)
        except TypeError as exc:
            logger.warning(
                "AgentRunner: ClaudeAgentOptions rejected a kwarg (%s). "
                "Falling back to safe fields only.", exc
            )
            safe_keys = {
                "model", "system_prompt", "max_turns", "allowed_tools",
                "disallowed_tools", "permission_mode", "effort",
                "max_budget_usd", "resume",
            }
            options = ClaudeAgentOptions(
                **{k: v for k, v in opts.items() if k in safe_keys}
            )

        return {"prompt": prompt, "options": options}

    # ------------------------------------------------------------------ #
    # Run — sync wrapper
    # ------------------------------------------------------------------ #
    def run(self, prompt: str, *, context: Optional[dict[str, Any]] = None) -> AgentResult:
        """Run the agent synchronously.

        Parameters
        ----------
        prompt:
            User task. Inject dynamic values directly:
            ``runner.run(f"Process {qty} items at ${price} each")``
        context:
            Ignored — accepted for protocol compatibility with
            :class:`~claudekit.agents.BudgetGuard` and
            :class:`~claudekit.agents.AgentInspector`.  The Agent SDK
            does not support a context dict; inject values into the
            prompt string instead.

        Returns
        -------
        AgentResult
        """
        if context is not None:
            logger.debug(
                "AgentRunner.run: context dict ignored — format values "
                "into the prompt string instead."
            )
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, self.run_async(prompt))
                return future.result()
        else:
            return asyncio.run(self.run_async(prompt))

    # ------------------------------------------------------------------ #
    # Run — direct API (no subprocess)
    # ------------------------------------------------------------------ #
    async def _run_direct_async(self, prompt: str) -> AgentResult:
        """Run via Anthropic SDK directly without spawning a subprocess.

        Used when ``direct=True`` is passed to the constructor.  Falls back
        to creating a temporary ``anthropic.AsyncAnthropic`` client when no
        *client* was supplied.
        """
        try:
            import anthropic  # type: ignore[import-untyped]
        except ImportError as exc:
            from claudekit.errors import ConfigurationError
            raise ConfigurationError(
                "anthropic SDK is not installed",
                code="CONFIGURATION_ERROR",
                recovery_hint="pip install anthropic",
                original=exc,
            ) from exc

        agent = self._agent
        client = self._direct_client
        owns_client = False
        if client is None:
            client = anthropic.AsyncAnthropic()
            owns_client = True

        model = agent.model or "claude-haiku-4-5-20251001"
        max_tokens = getattr(agent, "max_tokens", None) or 4096
        kwargs: Dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if agent.system:
            kwargs["system"] = agent.system

        logger.info(
            "Running agent '%s' (direct, model=%s): %s",
            agent.name, model, prompt[:120],
        )
        start = time.monotonic()

        try:
            raw_client = getattr(client, "_client", client)
            if hasattr(raw_client, "messages"):
                create = raw_client.messages.create
            else:
                create = client.messages.create

            if asyncio.iscoroutinefunction(create):
                response = await create(**kwargs)
            else:
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None, lambda: create(**kwargs)
                )
        finally:
            if owns_client and hasattr(client, "aclose"):
                await client.aclose()

        elapsed = time.monotonic() - start
        text = "".join(
            block.text
            for block in response.content
            if hasattr(block, "text")
        )
        return AgentResult(
            output=text,
            turns=1,
            duration_seconds=elapsed,
        )

    # ------------------------------------------------------------------ #
    # Run — async
    # ------------------------------------------------------------------ #
    async def run_async(self, prompt: str) -> AgentResult:
        """Run the agent asynchronously."""
        if self._direct:
            return await self._run_direct_async(prompt)

        sdk = self._ensure_sdk()
        kwargs = self._build_query_kwargs(prompt)

        logger.info(
            "Running agent '%s' (effort=%s): %s",
            self._agent.name, self._agent.effort, prompt[:120],
        )
        start = time.monotonic()

        try:
            if self._agent.timeout_seconds is not None:
                messages = await asyncio.wait_for(
                    self._collect_messages(sdk, kwargs),
                    timeout=self._agent.timeout_seconds,
                )
            else:
                messages = await self._collect_messages(sdk, kwargs)

        except asyncio.TimeoutError:
            from claudekit.errors import AgentTimeoutError
            elapsed = time.monotonic() - start
            raise AgentTimeoutError(
                f"Agent '{self._agent.name}' timed out after {elapsed:.1f}s "
                f"(limit: {self._agent.timeout_seconds}s)",
                context={
                    "agent": self._agent.name,
                    "timeout_seconds": self._agent.timeout_seconds,
                    "elapsed_seconds": round(elapsed, 2),
                },
            )

        elapsed = time.monotonic() - start
        result = self._parse_result(messages, elapsed)
        logger.info(
            "Agent '%s' done in %.2fs (%d turns)",
            self._agent.name, result.duration_seconds, result.turns,
        )
        return result

    # ------------------------------------------------------------------ #
    # Stream — async generator
    # ------------------------------------------------------------------ #
    async def stream(self, prompt: str) -> AsyncIterator[Any]:
        """Yield raw SDK messages as they arrive.

        Parameters
        ----------
        prompt:
            User task.

        Yields
        ------
        Any
            SystemMessage, AssistantMessage, ResultMessage objects.
        """
        sdk = self._ensure_sdk()
        kwargs = self._build_query_kwargs(prompt)
        query_fn = getattr(sdk, "query", None)
        if query_fn is None:
            from claudekit.errors import ConfigurationError
            raise ConfigurationError(
                "claude_agent_sdk does not expose a query function",
                code="CONFIGURATION_ERROR",
            )
        logger.info("Streaming agent '%s': %s", self._agent.name, prompt[:120])
        async for message in query_fn(**kwargs):
            yield message

    # ------------------------------------------------------------------ #
    # Resume
    # ------------------------------------------------------------------ #
    async def resume(self, session_id: str, prompt: str) -> AgentResult:
        """Resume a previous session.

        Parameters
        ----------
        session_id:
            The session_id from a prior AgentResult.
        prompt:
            Follow-up prompt.
        """
        sdk = self._ensure_sdk()
        kwargs = self._build_query_kwargs(prompt, session_id=session_id)
        logger.info(
            "Resuming agent '%s' session=%s", self._agent.name, session_id
        )
        start = time.monotonic()
        messages = await self._collect_messages(sdk, kwargs)
        elapsed = time.monotonic() - start
        return self._parse_result(messages, elapsed)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    async def _collect_messages(sdk: Any, kwargs: dict[str, Any]) -> list[Any]:
        """Drive the async generator and return all messages as a list."""
        query_fn = getattr(sdk, "query", None)
        if query_fn is None:
            from claudekit.errors import ConfigurationError
            raise ConfigurationError(
                "claude_agent_sdk does not expose a query function",
                code="CONFIGURATION_ERROR",
            )
        messages: list[Any] = []
        async for msg in query_fn(**kwargs):
            messages.append(msg)
        return messages

    @staticmethod
    def _parse_result(messages: list[Any], elapsed: float) -> AgentResult:
        """Extract output, turns, cost, session_id from SDK message list."""
        try:
            from claude_agent_sdk import (  # type: ignore[import-untyped]
                AssistantMessage, TextBlock, ResultMessage,
            )
            has_types = True
        except ImportError:
            has_types = False
            AssistantMessage = TextBlock = ResultMessage = None

        output = ""
        total_cost = 0.0
        turns = 0
        session_id: Optional[str] = None

        for msg in reversed(messages):
            # Extract text from the last AssistantMessage
            if has_types and isinstance(msg, AssistantMessage) and not output:
                for block in getattr(msg, "content", []):
                    if isinstance(block, TextBlock):
                        output = block.text
                        break

            # Extract stats from ResultMessage (always last)
            if has_types and isinstance(msg, ResultMessage):
                # SDK field is total_cost_usd (fallback to cost for compat)
                total_cost   = float(
                    getattr(msg, "total_cost_usd", None)
                    or getattr(msg, "cost", 0.0)
                    or 0.0
                )
                turns        = int(getattr(msg,   "num_turns",  0)  or 0)
                session_id   = getattr(msg, "session_id", None)
                if not output:
                    output = str(getattr(msg, "result", "") or "")
                break

        # Fallback string parsing when SDK types unavailable
        if not has_types and not output:
            for msg in reversed(messages):
                s = str(msg)
                if "TextBlock(text=" in s:
                    marker = "TextBlock(text='"
                    i = s.find(marker)
                    if i >= 0:
                        i += len(marker)
                        j = s.find("')", i)
                        output = s[i:j] if j > i else s[i:i + 300]
                        break

        return AgentResult(
            output=output,
            turns=turns,
            total_tokens=0,
            total_cost=total_cost,
            duration_seconds=round(elapsed, 4),
            messages=[str(m) for m in messages],
            session_id=session_id,
        )

    # ------------------------------------------------------------------ #
    # Properties
    # ------------------------------------------------------------------ #
    @property
    def agent(self) -> Any:
        """The :class:`~claudekit.agents.Agent` backing this runner."""
        return self._agent
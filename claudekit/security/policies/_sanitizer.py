"""Input sanitization policy.

:class:`InputSanitizerPolicy` applies a configurable set of transforms to
incoming messages before they reach the model.  This includes stripping
HTML, escaping XML entities, truncating oversized tool results, and
flagging instruction-like patterns that might indicate prompt injection.
"""

from __future__ import annotations

import html
import logging
import re
import warnings
from typing import Any, Callable, Dict, List, Optional

from claudekit.security._context import SecurityContext
from claudekit.security._policy import Policy

logger = logging.getLogger("claudekit.security.sanitizer")

# =========================================================================== #
# Built-in transforms
# =========================================================================== #

_HTML_TAG_RE = re.compile(r"<[^>]+>")

# Instruction-like patterns that might appear in tool results or user input
_INSTRUCTION_PATTERNS: List[re.Pattern[str]] = [
    re.compile(r"(?i)<\s*/?(?:system|instruction|prompt)\s*>"),
    re.compile(r"(?i)\[INST\]"),
    re.compile(r"(?i)\[/INST\]"),
    re.compile(r"(?i)<<\s*SYS\s*>>"),
    re.compile(r"(?i)<</SYS>>"),
    re.compile(r"(?i)^Human\s*:\s", re.MULTILINE),
    re.compile(r"(?i)^Assistant\s*:\s", re.MULTILINE),
]


def _strip_html(text: str) -> str:
    """Remove all HTML tags from *text*."""
    return _HTML_TAG_RE.sub("", text)


def _escape_xml(text: str) -> str:
    """Escape XML/HTML entities in *text*."""
    return html.escape(text, quote=True)


def _truncate(text: str, max_chars: int) -> str:
    """Truncate *text* to *max_chars*, appending an indicator if truncated."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n... [truncated]"


# =========================================================================== #
# Policy class
# =========================================================================== #


class InputSanitizerPolicy(Policy):
    """Sanitize input messages before they are sent to the model.

    Parameters
    ----------
    strip_html:
        If ``True``, strip all HTML tags from message content.
    escape_xml:
        If ``True``, escape XML/HTML entities in message content.
        Applied *after* ``strip_html`` if both are enabled.
    max_tool_result_chars:
        Maximum character length for tool-result content blocks.
        Longer results are truncated.  ``None`` means no limit.
    flag_instruction_patterns:
        If ``True``, emit a warning when instruction-like patterns
        (e.g. ``[INST]``, ``<system>``) are found in user or tool-result
        content.
    custom_transforms:
        Optional list of additional ``(str) -> str`` transform functions
        applied to each text block in order.
    """

    name: str = "input_sanitizer"

    def __init__(
        self,
        strip_html: bool = False,
        escape_xml: bool = False,
        max_tool_result_chars: Optional[int] = None,
        flag_instruction_patterns: bool = True,
        custom_transforms: Optional[List[Callable[[str], str]]] = None,
    ) -> None:
        self.strip_html = strip_html
        self.escape_xml = escape_xml
        self.max_tool_result_chars = max_tool_result_chars
        self.flag_instruction_patterns = flag_instruction_patterns
        self.custom_transforms: List[Callable[[str], str]] = list(
            custom_transforms or []
        )

    # ------------------------------------------------------------------ #
    # Hooks
    # ------------------------------------------------------------------ #

    def check_request(
        self,
        messages: List[Dict[str, Any]],
        context: SecurityContext,
    ) -> None:
        """Sanitize messages in-place before sending.

        This modifies the *messages* list directly.
        """
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content")

            if isinstance(content, str):
                msg["content"] = self._sanitize_text(content, role, context)
            elif isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    block_type = block.get("type", "")

                    # Handle text blocks
                    if "text" in block:
                        block["text"] = self._sanitize_text(
                            block["text"], role, context
                        )

                    # Handle tool_result content
                    if block_type == "tool_result":
                        self._sanitize_tool_result(block, context)

                    # Handle nested content in tool_result
                    inner_content = block.get("content")
                    if isinstance(inner_content, str):
                        block["content"] = self._sanitize_text(
                            inner_content, role, context
                        )
                    elif isinstance(inner_content, list):
                        for sub in inner_content:
                            if isinstance(sub, dict) and "text" in sub:
                                sub["text"] = self._sanitize_text(
                                    sub["text"], role, context
                                )

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _sanitize_text(
        self,
        text: str,
        role: str,
        context: SecurityContext,
    ) -> str:
        """Apply all configured transforms to a text string."""
        if self.strip_html:
            text = _strip_html(text)

        if self.escape_xml:
            text = _escape_xml(text)

        for transform in self.custom_transforms:
            text = transform(text)

        # Flag instruction patterns in non-system messages
        if self.flag_instruction_patterns and role != "system":
            for pat in _INSTRUCTION_PATTERNS:
                match = pat.search(text)
                if match:
                    logger.warning(
                        "Instruction-like pattern found in %s message: %r "
                        "(request_id=%s)",
                        role,
                        match.group(),
                        context.request_id,
                    )
                    warnings.warn(
                        f"Instruction-like pattern in {role} message: "
                        f"{match.group()!r}",
                        UserWarning,
                        stacklevel=4,
                    )
                    break  # One warning per text block is sufficient

        return text

    def _sanitize_tool_result(
        self,
        block: Dict[str, Any],
        context: SecurityContext,
    ) -> None:
        """Apply tool-result-specific sanitization (truncation)."""
        if self.max_tool_result_chars is None:
            return

        inner = block.get("content")
        if isinstance(inner, str) and len(inner) > self.max_tool_result_chars:
            original_len = len(inner)
            block["content"] = _truncate(inner, self.max_tool_result_chars)
            logger.info(
                "Truncated tool result from %d to %d chars (request_id=%s)",
                original_len,
                self.max_tool_result_chars,
                context.request_id,
            )
        elif isinstance(inner, list):
            for sub in inner:
                if isinstance(sub, dict) and "text" in sub:
                    text = sub["text"]
                    if isinstance(text, str) and len(text) > self.max_tool_result_chars:
                        original_len = len(text)
                        sub["text"] = _truncate(text, self.max_tool_result_chars)
                        logger.info(
                            "Truncated tool result block from %d to %d chars "
                            "(request_id=%s)",
                            original_len,
                            self.max_tool_result_chars,
                            context.request_id,
                        )


__all__ = ["InputSanitizerPolicy"]

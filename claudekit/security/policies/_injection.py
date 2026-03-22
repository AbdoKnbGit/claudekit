"""Prompt-injection detection policy.

:class:`PromptInjectionPolicy` scans incoming messages for patterns commonly
associated with prompt-injection attacks.  It supports three sensitivity levels
(``"low"``, ``"medium"``, ``"high"``), three actions (``"block"``, ``"warn"``,
``"sanitize"``), and optional caller-supplied custom patterns.

Detection categories
--------------------
* Instruction-override phrases (e.g. "ignore previous instructions")
* Identity-override phrases (e.g. "you are now", "pretend you are")
* Fake system prompts (``"SYSTEM:"`` in user/assistant content)
* Memory-wipe phrases ("forget everything", "disregard your")
* Suspicious base64 blobs (> 100 characters in user messages)
* Unicode direction overrides (RTL injection)
* Tool-result instruction-like phrases
* Multi-turn concatenation scanning
"""

from __future__ import annotations

import base64
import logging
import re
import warnings
from typing import Any, Dict, List, Optional

from claudekit.errors._base import PromptInjectionError
from claudekit.security._context import SecurityContext
from claudekit.security._policy import Policy

logger = logging.getLogger("claudekit.security.injection")

# =========================================================================== #
# Pattern banks by sensitivity
# =========================================================================== #

# Patterns included at LOW sensitivity and above
_LOW_PATTERNS: List[str] = [
    r"(?i)ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"(?i)SYSTEM\s*:",
    r"(?i)forget\s+everything",
    r"(?i)disregard\s+your\s",
]

# Additional patterns included at MEDIUM sensitivity and above
_MEDIUM_PATTERNS: List[str] = [
    r"(?i)you\s+are\s+now\b",
    r"(?i)pretend\s+you\s+are\b",
    r"(?i)act\s+as\s+if\s+you\s+are\b",
    r"(?i)new\s+instructions?\s*:",
    r"(?i)override\s+(all\s+)?instructions",
    r"(?i)reset\s+your\s+(instructions|prompt|rules)",
]

# Additional patterns included at HIGH sensitivity and above
_HIGH_PATTERNS: List[str] = [
    r"(?i)do\s+not\s+follow\s+(your|the)\s+(previous|original)",
    r"(?i)from\s+now\s+on\s+you\s+(will|must|should|are)",
    r"(?i)respond\s+only\s+with",
    r"(?i)translate\s+the\s+(above|previous|following)\s+to",
    r"(?i)repeat\s+(back\s+)?(the|your)\s+(system|initial)\s+(prompt|instructions)",
    r"(?i)what\s+(is|are)\s+your\s+(system|initial)\s+(prompt|instructions)",
    r"(?i)\bDAN\b.*\bjailbreak\b",
]

# Tool-result injection patterns (checked in tool_result content)
_TOOL_RESULT_PATTERNS: List[str] = [
    r"(?i)<\s*important\s*>",
    r"(?i)\[INST\]",
    r"(?i)\[/INST\]",
    r"(?i)<<\s*SYS\s*>>",
    r"(?i)Human\s*:\s*",
    r"(?i)Assistant\s*:\s*",
]

# Unicode direction-override code points used in RTL injection
_UNICODE_DIRECTION_OVERRIDES = re.compile(
    r"[\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069]"
)

# Base64 detection: contiguous base64-alphabet chars >= 100
_BASE64_BLOB = re.compile(r"[A-Za-z0-9+/=]{100,}")


def _compile_patterns(sensitivity: str, custom: Optional[List[str]]) -> List[re.Pattern[str]]:
    """Compile regex patterns for the given sensitivity level."""
    raw: List[str] = list(_LOW_PATTERNS)
    if sensitivity in ("medium", "high"):
        raw.extend(_MEDIUM_PATTERNS)
    if sensitivity == "high":
        raw.extend(_HIGH_PATTERNS)
    if custom:
        raw.extend(custom)
    return [re.compile(p) for p in raw]


def _extract_text(messages: List[Dict[str, Any]]) -> str:
    """Concatenate all user, assistant, and tool_result text for scanning."""
    parts: List[str] = []
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    text = block.get("text", "") or block.get("content", "")
                    if isinstance(text, str):
                        parts.append(text)
    return "\n".join(parts)


def _extract_user_text(messages: List[Dict[str, Any]]) -> str:
    """Extract only user-role text (for base64 scanning)."""
    parts: List[str] = []
    for msg in messages:
        if msg.get("role") != "user":
            continue
        content = msg.get("content", "")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    text = block.get("text", "") or block.get("content", "")
                    if isinstance(text, str):
                        parts.append(text)
    return "\n".join(parts)


def _extract_tool_results(messages: List[Dict[str, Any]]) -> str:
    """Extract tool_result content blocks for instruction-injection scanning."""
    parts: List[str] = []
    for msg in messages:
        if msg.get("role") != "user":
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                inner = block.get("content", "")
                if isinstance(inner, str):
                    parts.append(inner)
                elif isinstance(inner, list):
                    for sub in inner:
                        if isinstance(sub, dict):
                            text = sub.get("text", "")
                            if isinstance(text, str):
                                parts.append(text)
    return "\n".join(parts)


def _has_suspicious_base64(text: str) -> bool:
    """Return ``True`` if *text* contains a base64-like blob > 100 chars.

    We also attempt to decode the blob; if decoding succeeds and the result
    contains instruction-like keywords, it is flagged regardless of length.
    """
    for match in _BASE64_BLOB.finditer(text):
        blob = match.group()
        # Try decoding to see if the payload contains suspicious text
        try:
            decoded = base64.b64decode(blob, validate=True).decode("utf-8", errors="ignore")
            lower = decoded.lower()
            if any(kw in lower for kw in ("ignore", "system:", "pretend", "instructions")):
                return True
        except (re.error, TypeError, AttributeError):
            pass
        # Flag any blob exceeding 100 chars as suspicious
        return True
    return False


class PromptInjectionPolicy(Policy):
    """Detect and block prompt-injection attempts in incoming messages.

    Parameters
    ----------
    sensitivity:
        Detection sensitivity level: ``"low"``, ``"medium"``, or ``"high"``.
        Higher levels include more heuristic patterns and will produce more
        false positives.
    action:
        What to do when an injection is detected:

        * ``"block"`` -- raise :class:`~claudekit.errors.PromptInjectionError`.
        * ``"warn"`` -- emit a :class:`warnings.UserWarning` and allow the request.
        * ``"sanitize"`` -- strip the offending content and allow.
    custom_patterns:
        Optional list of additional regex patterns to flag.
    """

    name: str = "prompt_injection"

    def __init__(
        self,
        sensitivity: str = "medium",
        action: str = "block",
        custom_patterns: Optional[List[str]] = None,
    ) -> None:
        if sensitivity not in ("low", "medium", "high"):
            raise ValueError(
                f"sensitivity must be 'low', 'medium', or 'high', got {sensitivity!r}"
            )
        if action not in ("block", "warn", "sanitize"):
            raise ValueError(
                f"action must be 'block', 'warn', or 'sanitize', got {action!r}"
            )
        self.sensitivity = sensitivity
        self.action = action
        self.custom_patterns = custom_patterns
        self._compiled = _compile_patterns(sensitivity, custom_patterns)
        self._tool_patterns = [re.compile(p) for p in _TOOL_RESULT_PATTERNS]

    # ------------------------------------------------------------------ #
    # Policy hooks
    # ------------------------------------------------------------------ #

    def check_request(
        self,
        messages: List[Dict[str, Any]],
        context: SecurityContext,
    ) -> None:
        """Scan messages for prompt-injection patterns.

        Trusted callers (``context.trusted_caller is True``) bypass this
        check entirely.
        """
        if context.trusted_caller:
            logger.debug("Skipping injection check for trusted caller")
            return

        findings: List[str] = []

        # 1. Full-history pattern scan (multi-turn concatenation)
        full_text = _extract_text(messages)
        for pat in self._compiled:
            match = pat.search(full_text)
            if match:
                findings.append(f"Pattern match: {pat.pattern!r} -> {match.group()!r}")

        # 2. Unicode direction overrides (RTL injection)
        if _UNICODE_DIRECTION_OVERRIDES.search(full_text):
            findings.append("Unicode direction override characters detected")

        # 3. Suspicious base64 in user messages
        user_text = _extract_user_text(messages)
        if _has_suspicious_base64(user_text):
            findings.append("Suspicious base64-encoded blob in user message")

        # 4. Tool-result instruction injection
        tool_text = _extract_tool_results(messages)
        if tool_text:
            for pat in self._tool_patterns:
                match = pat.search(tool_text)
                if match:
                    findings.append(
                        f"Tool-result instruction injection: {pat.pattern!r} -> {match.group()!r}"
                    )

        if not findings:
            return

        detail = "; ".join(findings)
        logger.warning(
            "Prompt injection detected (action=%s): %s", self.action, detail
        )

        if self.action == "block":
            raise PromptInjectionError(
                f"Prompt injection detected: {detail}",
                context={"findings": findings, "request_id": context.request_id},
            )
        elif self.action == "warn":
            warnings.warn(
                f"Possible prompt injection: {detail}",
                UserWarning,
                stacklevel=2,
            )
        elif self.action == "sanitize":
            # Sanitize by stripping matched substrings from user content
            self._sanitize_messages(messages)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _sanitize_messages(self, messages: List[Dict[str, Any]]) -> None:
        """Strip injection patterns from user messages in-place."""
        for msg in messages:
            if msg.get("role") != "user":
                continue
            content = msg.get("content")
            if isinstance(content, str):
                msg["content"] = self._sanitize_text(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and "text" in block:
                        block["text"] = self._sanitize_text(block["text"])

    def _sanitize_text(self, text: str) -> str:
        """Remove matched patterns and suspicious content from *text*."""
        for pat in self._compiled:
            text = pat.sub("", text)
        # Remove Unicode direction overrides
        text = _UNICODE_DIRECTION_OVERRIDES.sub("", text)
        # Remove base64 blobs
        text = _BASE64_BLOB.sub("[SANITIZED]", text)
        return text


__all__ = ["PromptInjectionPolicy"]

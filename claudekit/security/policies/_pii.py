"""PII (Personally Identifiable Information) detection policy.

:class:`PIIPolicy` scans messages and/or responses for sensitive data such as
Social Security Numbers, credit-card numbers (with Luhn validation), email
addresses, phone numbers, passport numbers, API keys, and IP addresses.
"""

from __future__ import annotations

import logging
import re
import warnings
from typing import Any, Dict, List, Optional, Set

from claudekit.errors._base import PIIDetectedError
from claudekit.security._context import SecurityContext
from claudekit.security._policy import Policy

logger = logging.getLogger("claudekit.security.pii")

# =========================================================================== #
# PII type registry
# =========================================================================== #

ALL_PII_TYPES: List[str] = [
    "ssn",
    "credit_card",
    "email",
    "phone",
    "passport",
    "api_key",
    "ip_address",
    "medical_record",
    "dob",
    "tax_id",
    "bank_account",
]

# =========================================================================== #
# Regex patterns
# =========================================================================== #

_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

# Credit card: 13-19 digit sequences (possibly separated by spaces/dashes)
_CC_RAW_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")

_EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

# US phone: (xxx) xxx-xxxx, xxx-xxx-xxxx, +1xxxxxxxxxx, etc.
# International: +<country_code> <digits>, allowing spaces/dashes
_PHONE_RE = re.compile(
    r"(?:\+\d{1,3}[\s.-]?)?"           # optional country code
    r"(?:\(?\d{2,4}\)?[\s.-]?)?"        # optional area code
    r"\d{3,4}[\s.-]?\d{3,4}\b"         # main number
)

# Passport patterns: US (9 digits), UK (9 digits), etc.
_PASSPORT_RE = re.compile(
    r"\b(?:"
    r"[A-Z]{1,2}\d{6,9}"                # UK, DE, many EU countries
    r"|\d{9}"                            # US passport
    r"|[A-Z]\d{8}"                       # CA, IN
    r")\b"
)

# API key patterns
_API_KEY_RE = re.compile(
    r"\b(?:"
    r"sk-[A-Za-z0-9]{20,}"              # OpenAI / Stripe style
    r"|sk-ant-[A-Za-z0-9-]{20,}"        # Anthropic style
    r"|AKIA[A-Z0-9]{16}"                # AWS access key
    r"|ghp_[A-Za-z0-9]{36}"             # GitHub PAT
    r"|glpat-[A-Za-z0-9_-]{20,}"        # GitLab PAT
    r"|xox[bpars]-[A-Za-z0-9-]{10,}"    # Slack token
    r"|AIza[A-Za-z0-9_-]{35}"           # Google API key
    r")\b"
)

# IPv4
_IPV4_RE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
)

# IPv6 (simplified)
_IPV6_RE = re.compile(r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b")

# Medical record number (MRN) -- common format: MRN followed by digits
_MEDICAL_RECORD_RE = re.compile(r"\b(?:MRN|mrn)[#:\s-]*\d{5,12}\b")

# Date of birth patterns
_DOB_RE = re.compile(
    r"\b(?:"
    r"(?:0[1-9]|1[0-2])[/-](?:0[1-9]|[12]\d|3[01])[/-](?:19|20)\d{2}"  # MM/DD/YYYY
    r"|(?:19|20)\d{2}[/-](?:0[1-9]|1[0-2])[/-](?:0[1-9]|[12]\d|3[01])"  # YYYY-MM-DD
    r")\b"
)

# Tax ID (EIN, ITIN, etc.)
_TAX_ID_RE = re.compile(r"\b\d{2}-\d{7}\b")

# Bank account numbers (US: 8-17 digits)
_BANK_ACCOUNT_RE = re.compile(r"\b\d{8,17}\b")


def _luhn_check(number: str) -> bool:
    """Validate a number string using the Luhn algorithm.

    Parameters
    ----------
    number:
        A string of digits (no spaces or dashes).

    Returns
    -------
    bool
        ``True`` if the number passes the Luhn checksum.
    """
    digits = [int(d) for d in number]
    # Reverse, double every second digit
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    total = sum(odd_digits)
    for d in even_digits:
        doubled = d * 2
        total += doubled if doubled < 10 else doubled - 9
    return total % 10 == 0


def _strip_separators(text: str) -> str:
    """Remove spaces and dashes from a potential card number."""
    return re.sub(r"[\s-]", "", text)


# =========================================================================== #
# Detector registry
# =========================================================================== #

_DETECTOR_MAP: Dict[str, Any] = {
    "ssn": _SSN_RE,
    "credit_card": _CC_RAW_RE,  # requires Luhn post-filter
    "email": _EMAIL_RE,
    "phone": _PHONE_RE,
    "passport": _PASSPORT_RE,
    "api_key": _API_KEY_RE,
    "ip_address": [_IPV4_RE, _IPV6_RE],
    "medical_record": _MEDICAL_RECORD_RE,
    "dob": _DOB_RE,
    "tax_id": _TAX_ID_RE,
    "bank_account": _BANK_ACCOUNT_RE,
}


def _find_pii(text: str, types: Set[str]) -> Dict[str, List[str]]:
    """Scan *text* for PII of the requested *types*.

    Returns a dict mapping PII type names to lists of matched strings.
    """
    found: Dict[str, List[str]] = {}
    for pii_type in types:
        detector = _DETECTOR_MAP.get(pii_type)
        if detector is None:
            continue

        regexes = detector if isinstance(detector, list) else [detector]
        matches: List[str] = []

        for regex in regexes:
            for m in regex.finditer(text):
                matched = m.group()
                # Credit card: apply Luhn validation
                if pii_type == "credit_card":
                    digits = _strip_separators(matched)
                    if not digits.isdigit() or len(digits) < 13 or len(digits) > 19:
                        continue
                    if not _luhn_check(digits):
                        continue
                # Bank account: avoid false positives with short digit runs
                # Only flag if preceded by account-like context
                if pii_type == "bank_account":
                    # Simple heuristic: look for "account" keyword nearby
                    start = max(0, m.start() - 40)
                    context_text = text[start:m.start()].lower()
                    if "account" not in context_text and "acct" not in context_text:
                        continue
                matches.append(matched)

        if matches:
            found[pii_type] = matches

    return found


def _redact_pii(text: str, types: Set[str], redact_with: str) -> str:
    """Replace detected PII in *text* with *redact_with*.

    Returns the redacted text.
    """
    for pii_type in types:
        detector = _DETECTOR_MAP.get(pii_type)
        if detector is None:
            continue

        regexes = detector if isinstance(detector, list) else [detector]

        for regex in regexes:
            if pii_type == "credit_card":

                def _cc_replacer(m: re.Match[str]) -> str:
                    digits = _strip_separators(m.group())
                    if (
                        digits.isdigit()
                        and 13 <= len(digits) <= 19
                        and _luhn_check(digits)
                    ):
                        return redact_with
                    return m.group()

                text = regex.sub(_cc_replacer, text)
            elif pii_type == "bank_account":

                def _bank_replacer(m: re.Match[str]) -> str:
                    start = max(0, m.start() - 40)
                    context_text = text[start:m.start()].lower()
                    if "account" in context_text or "acct" in context_text:
                        return redact_with
                    return m.group()

                text = regex.sub(_bank_replacer, text)
            else:
                text = regex.sub(redact_with, text)

    return text


# =========================================================================== #
# Response text extraction
# =========================================================================== #


def _extract_response_text(response: Any) -> str:
    """Best-effort extraction of text from an API response object."""
    # Handle dict responses
    if isinstance(response, dict):
        content = response.get("content", [])
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: List[str] = []
            for block in content:
                if isinstance(block, dict):
                    parts.append(block.get("text", ""))
                elif isinstance(block, str):
                    parts.append(block)
            return "\n".join(parts)
        return ""

    # Handle Anthropic SDK Message objects (duck-typing)
    content = getattr(response, "content", None)
    if content is not None:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                text = getattr(block, "text", None)
                if text:
                    parts.append(text)
                elif isinstance(block, dict):
                    parts.append(block.get("text", ""))
            return "\n".join(parts)

    return str(response)


def _redact_response_text(response: Any, types: Set[str], redact_with: str) -> Any:
    """Redact PII in a response object, returning the modified response."""
    if isinstance(response, dict):
        content = response.get("content", [])
        if isinstance(content, str):
            response["content"] = _redact_pii(content, types, redact_with)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and "text" in block:
                    block["text"] = _redact_pii(block["text"], types, redact_with)
        return response

    # For SDK objects, try attribute mutation
    content = getattr(response, "content", None)
    if content is not None and isinstance(content, list):
        for block in content:
            text = getattr(block, "text", None)
            if text is not None:
                try:
                    block.text = _redact_pii(text, types, redact_with)
                except AttributeError:
                    pass

    return response


# =========================================================================== #
# Policy class
# =========================================================================== #


class PIIPolicy(Policy):
    """Detect and handle personally identifiable information in messages.

    Parameters
    ----------
    scan_requests:
        Whether to scan outbound request messages.
    scan_responses:
        Whether to scan inbound model responses.
    detect:
        List of PII types to detect (e.g. ``["ssn", "credit_card"]``).
        Defaults to all types except ``"ip_address"`` and ``"bank_account"``.
    action:
        ``"block"``, ``"redact"``, or ``"warn"``.
    redact_with:
        Replacement string when *action* is ``"redact"``.
    allow_in_system:
        If ``True``, system-role messages are excluded from scanning.
    """

    name: str = "pii"

    _DEFAULT_DETECT: List[str] = [
        "ssn",
        "credit_card",
        "email",
        "phone",
        "passport",
        "api_key",
    ]

    def __init__(
        self,
        scan_requests: bool = True,
        scan_responses: bool = True,
        detect: Optional[List[str]] = None,
        action: str = "redact",
        redact_with: str = "[REDACTED]",
        allow_in_system: bool = True,
    ) -> None:
        if action not in ("block", "redact", "warn"):
            raise ValueError(
                f"action must be 'block', 'redact', or 'warn', got {action!r}"
            )
        self.scan_requests = scan_requests
        self.scan_responses = scan_responses
        self.detect_types: Set[str] = set(detect or self._DEFAULT_DETECT)
        self.action = action
        self.redact_with = redact_with
        self.allow_in_system = allow_in_system

        # Validate requested types
        unknown = self.detect_types - set(ALL_PII_TYPES)
        if unknown:
            raise ValueError(f"Unknown PII types: {unknown!r}. Valid types: {ALL_PII_TYPES}")

    # ------------------------------------------------------------------ #
    # Hooks
    # ------------------------------------------------------------------ #

    def check_request(
        self,
        messages: List[Dict[str, Any]],
        context: SecurityContext,
    ) -> None:
        """Scan request messages for PII."""
        if not self.scan_requests:
            return

        text = self._extract_messages_text(messages)
        found = _find_pii(text, self.detect_types)
        if not found:
            return

        self._handle_finding(found, "request", context)

    def check_response(
        self,
        response: Any,
        context: SecurityContext,
    ) -> Any:
        """Scan response for PII, optionally redacting."""
        if not self.scan_responses:
            return response

        text = _extract_response_text(response)
        found = _find_pii(text, self.detect_types)
        if not found:
            return response

        if self.action == "redact":
            logger.info(
                "Redacting PII types %s in response (request_id=%s)",
                list(found.keys()),
                context.request_id,
            )
            return _redact_response_text(response, self.detect_types, self.redact_with)

        self._handle_finding(found, "response", context)
        return response

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _extract_messages_text(self, messages: List[Dict[str, Any]]) -> str:
        """Extract scannable text from messages, respecting allow_in_system."""
        parts: List[str] = []
        for msg in messages:
            if self.allow_in_system and msg.get("role") == "system":
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

    def _handle_finding(
        self,
        found: Dict[str, List[str]],
        location: str,
        context: SecurityContext,
    ) -> None:
        """Handle a PII finding according to the configured action."""
        type_names = list(found.keys())
        count = sum(len(v) for v in found.values())
        detail = f"PII detected in {location}: {count} instance(s) of types {type_names}"

        logger.warning("%s (request_id=%s)", detail, context.request_id)

        if self.action == "block":
            raise PIIDetectedError(
                detail,
                context={
                    "pii_types": type_names,
                    "count": count,
                    "request_id": context.request_id,
                },
            )
        elif self.action == "warn":
            warnings.warn(detail, UserWarning, stacklevel=3)


__all__ = ["PIIPolicy", "ALL_PII_TYPES"]

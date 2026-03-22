"""Machine-readable error code constants for all claudekit errors.

Every :class:`~claudekit.errors.ClaudekitError` carries one of these codes in
its ``code`` attribute so that callers can programmatically react to specific
failure modes without parsing human-readable messages.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
PROMPT_INJECTION_DETECTED: str = "PROMPT_INJECTION_DETECTED"
PII_DETECTED: str = "PII_DETECTED"
JAILBREAK_DETECTED: str = "JAILBREAK_DETECTED"
OUTPUT_VALIDATION_FAILED: str = "OUTPUT_VALIDATION_FAILED"
TOOL_BLOCKED: str = "TOOL_BLOCKED"
PRICE_DISCLOSURE_DETECTED: str = "PRICE_DISCLOSURE_DETECTED"

# ---------------------------------------------------------------------------
# Budget / Rate
# ---------------------------------------------------------------------------
BUDGET_EXCEEDED: str = "BUDGET_EXCEEDED"
RATE_LIMIT_EXCEEDED: str = "RATE_LIMIT_EXCEEDED"
TOKEN_LIMIT_EXCEEDED: str = "TOKEN_LIMIT_EXCEEDED"

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------
AGENT_TIMEOUT: str = "AGENT_TIMEOUT"
AGENT_MAX_TURNS: str = "AGENT_MAX_TURNS"
DELEGATION_LOOP: str = "DELEGATION_LOOP"

# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------
MEMORY_BACKEND_ERROR: str = "MEMORY_BACKEND_ERROR"
MEMORY_KEY_NOT_FOUND: str = "MEMORY_KEY_NOT_FOUND"
MEMORY_VALUE_TOO_LARGE: str = "MEMORY_VALUE_TOO_LARGE"

# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------
TOOL_INPUT_VALIDATION_FAILED: str = "TOOL_INPUT_VALIDATION_FAILED"
TOOL_RESULT_TOO_LARGE: str = "TOOL_RESULT_TOO_LARGE"
TOOL_JSON_ERROR: str = "TOOL_JSON_ERROR"

# ---------------------------------------------------------------------------
# Batch
# ---------------------------------------------------------------------------
BATCH_NOT_READY: str = "BATCH_NOT_READY"
BATCH_CANCELLED: str = "BATCH_CANCELLED"
BATCH_PARTIAL_FAILURE: str = "BATCH_PARTIAL_FAILURE"

# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------
SESSION_PAUSED: str = "SESSION_PAUSED"
SESSION_TERMINATED: str = "SESSION_TERMINATED"
SESSION_NAME_CONFLICT: str = "SESSION_NAME_CONFLICT"
SESSION_BUDGET_EXCEEDED: str = "SESSION_BUDGET_EXCEEDED"

# ---------------------------------------------------------------------------
# Precheck
# ---------------------------------------------------------------------------
CONTEXT_WINDOW_EXCEEDED: str = "CONTEXT_WINDOW_EXCEEDED"

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MISSING_API_KEY: str = "MISSING_API_KEY"
DEPRECATED_MODEL: str = "DEPRECATED_MODEL"
PLATFORM_NOT_AVAILABLE: str = "PLATFORM_NOT_AVAILABLE"
CONFIGURATION_ERROR: str = "CONFIGURATION_ERROR"

# ---------------------------------------------------------------------------
# SDK wrapper
# ---------------------------------------------------------------------------
OVERLOADED: str = "OVERLOADED"
API_CONNECTION_ERROR: str = "API_CONNECTION_ERROR"
API_TIMEOUT: str = "API_TIMEOUT"

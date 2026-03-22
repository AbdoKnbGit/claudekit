"""Security context passed through every policy check.

The :class:`SecurityContext` carries identity, timing, and metadata that
policies use to make access-control and auditing decisions.  A fresh context
is created for every request/response pair by :class:`~claudekit.security.SecurityLayer`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class SecurityContext:
    """Immutable-ish bag of per-request metadata consumed by policies.

    Parameters
    ----------
    user_id:
        Caller-supplied user identifier.  ``None`` for anonymous requests.
    request_id:
        Unique ID for this request.  Auto-generated as a UUID4 hex string
        when left empty.
    model:
        The Claude model identifier associated with this request
        (e.g. ``"claude-sonnet-4-20250514"``).
    timestamp:
        Wall-clock time at which the context was created.
    metadata:
        Arbitrary key/value pairs that policies or audit hooks may inspect.
    trusted_caller:
        When ``True``, prompt-injection and jailbreak policies will skip
        their checks.  Use this only for internal agent-to-agent calls
        where the input is fully trusted.
    """

    user_id: Optional[str] = None
    request_id: str = ""
    model: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    trusted_caller: bool = False

    def __post_init__(self) -> None:
        if not self.request_id:
            self.request_id = uuid.uuid4().hex


__all__ = ["SecurityContext"]

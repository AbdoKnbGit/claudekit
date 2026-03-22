"""Helper to inject memory context into a conversation's message list.

The :func:`context_with_memory` function prepends a system-message addendum
containing relevant memories so the model has access to cross-session context
without the caller needing to manage prompt construction manually.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from claudekit.memory._store import MemoryStore

logger = logging.getLogger(__name__)


def context_with_memory(
    messages: list[dict[str, Any]],
    memory_store: MemoryStore,
    *,
    scope: str | None = None,
    limit: int = 5,
) -> tuple[list[dict[str, Any]], Optional[str]]:
    """Return *(messages, system_addendum)* enriched with relevant memories.

    This inspects the most recent user message to build a search query,
    retrieves up to *limit* matching entries from *memory_store*, and
    returns the memory content as a plain string suitable for the top-level
    ``system`` parameter of the Anthropic Messages API.

    The Anthropic API does not accept ``role: "system"`` inside the
    ``messages`` array — memory context must be passed via the ``system``
    parameter instead.

    If the memory store is empty or no matches are found, returns
    ``(messages_copy, None)``.

    Parameters
    ----------
    messages:
        The current conversation history, each item a dict with at least
        a ``"role"`` and ``"content"`` key.
    memory_store:
        The :class:`MemoryStore` to query.
    scope:
        Optional namespace to restrict the memory search.
    limit:
        Maximum number of memory entries to include.

    Returns
    -------
    tuple[list[dict[str, Any]], Optional[str]]
        A 2-tuple of *(messages_copy, system_addendum_or_None)*.
        The caller should merge *system_addendum* into the ``system``
        parameter::

            msgs, extra = context_with_memory(messages, store)
            system = (base_system + "\\n\\n" + extra) if extra else base_system
            client.messages.create(..., system=system, messages=msgs)

    Examples
    --------
    >>> from claudekit.memory import MemoryStore, context_with_memory
    >>> store = MemoryStore()
    >>> store.save("user-pref", "Prefers concise answers")
    >>> msgs = [{"role": "user", "content": "Tell me about memory."}]
    >>> enriched_msgs, system_extra = context_with_memory(msgs, store)
    """
    # Find the most recent user message to use as the search query.
    query: str | None = None
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                query = content
            elif isinstance(content, list):
                # Handle structured content blocks.
                text_parts = [
                    block.get("text", "")
                    for block in content
                    if isinstance(block, dict) and block.get("type") == "text"
                ]
                query = " ".join(text_parts)
            break

    if not query:
        logger.debug("No user message found; skipping memory injection.")
        return list(messages), None

    # Search the memory store.
    entries = memory_store.search(query, scope=scope, limit=limit)
    if not entries:
        logger.debug("No matching memories found for query.")
        return list(messages), None

    # Format memory entries as a system addendum.
    lines: list[str] = ["[Relevant memories from previous sessions]"]
    for entry in entries:
        scope_tag = f" (scope: {entry.scope})" if entry.scope else ""
        lines.append(f"- {entry.key}{scope_tag}: {entry.value}")

    memory_block = "\n".join(lines)

    logger.debug(
        "Injecting %d memory entries into conversation context.",
        len(entries),
    )
    return list(messages), memory_block

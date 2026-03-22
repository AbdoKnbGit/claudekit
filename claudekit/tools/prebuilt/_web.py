"""Prebuilt web tools for search and fetching.

Provides ``web_search`` and ``web_fetch`` tools that use ``httpx`` for HTTP
requests. The ``httpx`` dependency is lazily imported and the tools degrade
gracefully when a URL is unreachable.

Example::

    from claudekit.tools.prebuilt import web_search, web_fetch

    results = web_search("Python asyncio tutorial", num_results=3)
    page = web_fetch("https://example.com")
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from claudekit.tools._decorator import tool

logger = logging.getLogger(__name__)


def _require_httpx() -> Any:
    """Lazily import httpx, raising a clear error if not installed.

    Returns:
        The ``httpx`` module.

    Raises:
        PlatformNotAvailableError: If ``httpx`` is not installed.
    """
    try:
        import httpx
        return httpx
    except ImportError:
        from claudekit.errors import PlatformNotAvailableError
        raise PlatformNotAvailableError(
            package="web",
            feature="web tools (web_search, web_fetch)",
        )


def _extract_text_from_html(html: str) -> str:
    """Extract readable text from HTML content.

    Strips tags and normalises whitespace for a plain-text representation.

    Args:
        html: Raw HTML string.

    Returns:
        Plain text extracted from the HTML.
    """
    # Remove script and style elements
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Decode common HTML entities
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&nbsp;", " ").replace("&#39;", "'")
    # Normalise whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


@tool
def web_search(query: str, num_results: int = 5) -> list[dict[str, str]]:
    """Search the web and return a list of results.

    Uses a simple HTTP-based search approach. Each result contains a title,
    URL, and snippet.

    Args:
        query: The search query string.
        num_results: Maximum number of results to return. Defaults to 5.

    Returns:
        A list of dictionaries, each with 'title', 'url', and 'snippet' keys.
    """
    httpx = _require_httpx()

    results: list[dict[str, str]] = []

    try:
        # Use DuckDuckGo HTML search (no API key needed)
        response = httpx.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; claudekit/0.1; "
                    "+https://github.com/claudekit/claudekit)"
                ),
            },
            timeout=15.0,
            follow_redirects=True,
        )
        response.raise_for_status()

        html = response.text

        # Parse DuckDuckGo HTML results
        # Each result is in a div with class "result"
        result_blocks = re.findall(
            r'<div[^>]*class="[^"]*result[^"]*"[^>]*>(.*?)</div>\s*</div>',
            html,
            re.DOTALL,
        )

        for block in result_blocks[:num_results]:
            # Extract title and URL
            title_match = re.search(
                r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
                block,
                re.DOTALL,
            )
            snippet_match = re.search(
                r'<a[^>]*class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>',
                block,
                re.DOTALL,
            )

            if title_match:
                url = title_match.group(1)
                title = re.sub(r"<[^>]+>", "", title_match.group(2)).strip()
                snippet = ""
                if snippet_match:
                    snippet = re.sub(r"<[^>]+>", "", snippet_match.group(1)).strip()

                results.append({
                    "title": title,
                    "url": url,
                    "snippet": snippet,
                })

    except (OSError, ValueError, TypeError):
        logger.exception("Web search failed for query %r.", query)
        results.append({
            "title": "Search Error",
            "url": "",
            "snippet": f"Web search failed for query: {query}. The search service may be unavailable.",
        })

    if not results:
        results.append({
            "title": "No Results",
            "url": "",
            "snippet": f"No results found for query: {query}",
        })

    return results


@tool
def web_fetch(url: str, extract_text: bool = True) -> str:
    """Fetch the content of a web page.

    Retrieves the page at the given URL and optionally extracts plain text
    from the HTML response.

    Args:
        url: The URL to fetch.
        extract_text: If True, strip HTML tags and return plain text.
            If False, return the raw HTML. Defaults to True.

    Returns:
        The page content as a string. Returns an error message if the
        request fails.
    """
    httpx = _require_httpx()

    try:
        response = httpx.get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; claudekit/0.1; "
                    "+https://github.com/claudekit/claudekit)"
                ),
            },
            timeout=30.0,
            follow_redirects=True,
        )
        response.raise_for_status()

        content = response.text

        if extract_text and "text/html" in response.headers.get("content-type", ""):
            content = _extract_text_from_html(content)

        return content

    except Exception as exc:
        error_msg = f"Failed to fetch {url}: {type(exc).__name__}: {exc}"
        logger.warning(error_msg)
        return error_msg

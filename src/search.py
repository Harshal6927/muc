# Copyright (c) 2025. All rights reserved.
"""Sound search functionality with fuzzy matching."""

from difflib import SequenceMatcher
from typing import Any, NamedTuple

from .logging_config import get_logger

logger = get_logger(__name__)


class SearchResult(NamedTuple):
    """A search result with relevance score."""

    name: str
    score: float
    match_type: str  # "exact", "prefix", "contains", "fuzzy"


def fuzzy_match(query: str, text: str) -> float:
    """Calculate fuzzy match score (0.0 to 1.0).

    Args:
        query: Search query
        text: Text to match against

    Returns:
        Match score from 0.0 (no match) to 1.0 (exact match)

    """
    query = query.lower()
    text = text.lower()

    # Exact match
    if query == text:
        return 1.0

    # Prefix match
    if text.startswith(query):
        return 0.9 + (len(query) / len(text)) * 0.1

    # Contains match
    if query in text:
        return 0.7 + (len(query) / len(text)) * 0.2

    # Fuzzy match using SequenceMatcher
    ratio = SequenceMatcher(None, query, text).ratio()
    return ratio * 0.6


def search_sounds(
    query: str,
    sounds: dict[str, Any],
    tags: dict[str, list[str]] | None = None,
    limit: int = 10,
    min_score: float = 0.3,
) -> list[SearchResult]:
    """Search for sounds by name and optionally tags.

    Args:
        query: Search query
        sounds: Dict of sound names to paths
        tags: Optional dict of sound names to tag lists
        limit: Maximum results to return
        min_score: Minimum match score (0.0 to 1.0)

    Returns:
        List of SearchResults sorted by relevance

    """
    results: list[SearchResult] = []
    query = query.lower().strip()

    if not query:
        return []

    logger.debug(f"Searching for '{query}' in {len(sounds)} sounds")

    for name in sounds:
        # Search in name
        name_score = fuzzy_match(query, name)

        # Search in tags
        tag_score = 0.0
        if tags and name in tags:
            for tag in tags[name]:
                tag_match = fuzzy_match(query, tag)
                tag_score = max(tag_score, tag_match * 0.8)  # Tags weighted slightly less

        # Best score wins
        best_score = max(name_score, tag_score)

        if best_score >= min_score:
            # Determine match type
            name_lower = name.lower()
            if name_lower == query:
                match_type = "exact"
            elif name_lower.startswith(query):
                match_type = "prefix"
            elif query in name_lower:
                match_type = "contains"
            else:
                match_type = "fuzzy"

            results.append(SearchResult(name, best_score, match_type))

    # Sort by score descending
    results.sort(key=lambda r: r.score, reverse=True)

    logger.debug(f"Found {len(results)} results for '{query}'")

    return results[:limit]


def highlight_match(text: str, query: str) -> str:
    """Highlight matching portions in text for Rich display.

    Args:
        text: Original text
        query: Search query to highlight

    Returns:
        Text with Rich markup for highlighting

    """
    query_lower = query.lower()
    text_lower = text.lower()

    idx = text_lower.find(query_lower)
    if idx == -1:
        return text

    before = text[:idx]
    match = text[idx : idx + len(query)]
    after = text[idx + len(query) :]

    return f"{before}[bold cyan]{match}[/bold cyan]{after}"

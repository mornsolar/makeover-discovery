"""schema.org JSON-LD extraction.

Preferred over scraping the rendered page: a business that publishes structured
data has told us what it is, rather than leaving us to infer it from markup that
changes with the next theme update.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any, Final

from bs4 import BeautifulSoup

BUSINESS_TYPES: Final = frozenset(
    {
        "localbusiness",
        "restaurant",
        "cafeorcoffeeshop",
        "bakery",
        "barorpub",
        "store",
        "hairsalon",
        "beautysalon",
        "healthandbeautybusiness",
        "medicalbusiness",
        "dentist",
        "hotel",
        "lodgingbusiness",
        "foodestablishment",
        "organization",
    }
)
"""schema.org types worth reading.

Matched case-insensitively and without the ``schema.org`` prefix, because sites
write the same type half a dozen different ways.
"""


def iter_business_nodes(soup: BeautifulSoup) -> Iterator[dict[str, Any]]:
    """Yield every JSON-LD node that describes a business.

    Walks nested graphs: many CMS plugins wrap everything in ``@graph``, and the
    business node is rarely the top-level object.
    """
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        text = script.string or script.get_text()
        if not text:
            continue
        try:
            document = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            # A malformed block is common and never worth failing the page for.
            continue
        yield from _walk(document)


def _walk(node: Any) -> Iterator[dict[str, Any]]:
    if isinstance(node, list):
        for item in node:
            yield from _walk(item)
        return
    if not isinstance(node, dict):
        return
    if _is_business(node):
        yield node
    for value in node.values():
        if isinstance(value, list | dict):
            yield from _walk(value)


def _is_business(node: dict[str, Any]) -> bool:
    declared = node.get("@type")
    candidates = declared if isinstance(declared, list) else [declared]
    return any(
        isinstance(value, str) and value.split("/")[-1].casefold() in BUSINESS_TYPES
        for value in candidates
    )


def first_string(node: dict[str, Any], *keys: str) -> str | None:
    """First usable string among ``keys``, flattening the shapes sites actually use."""
    for key in keys:
        value = _as_string(node.get(key))
        if value is not None:
            return value
    return None


def _as_string(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return " ".join(value.split())
    if isinstance(value, list):
        for item in value:
            found = _as_string(item)
            if found is not None:
                return found
    if isinstance(value, dict):
        # Handles ``{"@value": "..."}`` and image objects carrying ``url``.
        return _as_string(value.get("@value") or value.get("url") or value.get("name"))
    return None


def all_strings(node: dict[str, Any], *keys: str) -> tuple[str, ...]:
    """Every string found under ``keys``, in order, de-duplicated."""
    found: dict[str, None] = {}
    for key in keys:
        value = node.get(key)
        items = value if isinstance(value, list) else [value]
        for item in items:
            text = _as_string(item)
            if text is not None:
                found.setdefault(text, None)
    return tuple(found)

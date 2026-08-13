"""HTML content extraction.

Structured data first, page furniture second. A business that publishes JSON-LD
has stated what it is; Open Graph tags are the next best thing; the ``<title>``
is a last resort. Reading them in that order means a site redesign degrades the
result rather than breaking it.
"""

from __future__ import annotations

from typing import Final
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

from makeover_discovery.domain.model.web import (
    MAX_DESCRIPTORS,
    MAX_PHOTOS,
    ExtractedContent,
    FetchedPage,
)
from makeover_discovery.infrastructure.extract.jsonld import (
    all_strings,
    first_string,
    iter_business_nodes,
)

PARSER: Final = "lxml"
MAX_DESCRIPTION_CHARS: Final = 1000
MAX_NAME_CHARS: Final = 200
MAX_PHONE_CHARS: Final = 64


class HtmlContentExtractor:
    """Reads the handful of facts a design brief needs out of a page."""

    def extract(self, page: FetchedPage) -> ExtractedContent:
        soup = BeautifulSoup(page.html, PARSER)
        node = next(iter_business_nodes(soup), None)

        name = _cap(
            (first_string(node, "name", "legalName") if node else None) or _og(soup, "site_name"),
            MAX_NAME_CHARS,
        )
        description = _cap(
            (first_string(node, "description") if node else None)
            or _og(soup, "description")
            or _meta(soup, "description"),
            MAX_DESCRIPTION_CHARS,
        )
        phone = _cap(
            first_string(node, "telephone") if node else None,
            MAX_PHONE_CHARS,
        )

        return ExtractedContent(
            name=name or _cap(_title(soup), MAX_NAME_CHARS),
            description=description,
            phone=phone,
            descriptors=_descriptors(soup, node),
            photo_urls=_photos(soup, node, page.final_url),
        )


def _descriptors(soup: BeautifulSoup, node: dict[str, object] | None) -> tuple[str, ...]:
    found: dict[str, None] = {}
    if node is not None:
        for value in all_strings(node, "servesCuisine", "keywords", "amenityFeature"):
            found.setdefault(value, None)
    for value in (_meta(soup, "keywords") or "").split(","):
        cleaned = " ".join(value.split())
        if cleaned:
            found.setdefault(cleaned, None)
    return tuple(found)[:MAX_DESCRIPTORS]


def _photos(
    soup: BeautifulSoup,
    node: dict[str, object] | None,
    base_url: str,
) -> tuple[str, ...]:
    candidates: list[str] = []
    if node is not None:
        candidates.extend(all_strings(node, "image", "photo", "logo"))
    og_image = _og(soup, "image")
    if og_image:
        candidates.append(og_image)

    absolute: dict[str, None] = {}
    for candidate in candidates:
        # Relative image paths are common and useless to a downstream renderer,
        # so they are resolved against the URL we actually landed on.
        resolved = urljoin(base_url, candidate)
        if urlsplit(resolved).scheme in {"http", "https"}:
            absolute.setdefault(resolved, None)
    return tuple(absolute)[:MAX_PHOTOS]


def _og(soup: BeautifulSoup, name: str) -> str | None:
    return _content(soup.find("meta", attrs={"property": f"og:{name}"}))


def _meta(soup: BeautifulSoup, name: str) -> str | None:
    return _content(soup.find("meta", attrs={"name": name}))


def _content(tag: object) -> str | None:
    if not isinstance(tag, Tag):
        return None
    value = tag.get("content")
    if not isinstance(value, str):
        return None
    collapsed = " ".join(value.split())
    return collapsed or None


def _title(soup: BeautifulSoup) -> str | None:
    if soup.title is None or soup.title.string is None:
        return None
    collapsed = " ".join(soup.title.string.split())
    return collapsed or None


def _cap(value: str | None, max_chars: int) -> str | None:
    if value is None:
        return None
    collapsed = " ".join(value.split())
    return collapsed[:max_chars] or None

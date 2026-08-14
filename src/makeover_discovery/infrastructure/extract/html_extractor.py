"""HTML content extraction.

Structured data first, page furniture second. A business that publishes JSON-LD
has stated what it is; Open Graph tags are the next best thing; the ``<title>``
is a last resort. Reading them in that order means a site redesign degrades the
result rather than breaking it. Photo extraction follows the same escalation:
JSON-LD, then Open Graph/Twitter Card meta tags, then - only when nothing
structured said anything - a scan of the page's own ``<img>`` tags, since most
small-business sites never publish either.
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

MIN_IMG_DIMENSION_PX: Final = 200
"""Below this, a generic ``<img>`` is more likely UI furniture (an icon, a
divider, a tracking pixel) than a photo of the business - only applied when
the tag actually states a size; most real photos state none at all."""

_ICON_SRC_HINTS: Final = ("logo", "icon", "sprite", "avatar", "pixel", "spinner", "placeholder")
_IMG_SRC_ATTRS: Final = ("src", "data-src", "data-lazy-src")


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
    twitter_image = _meta(soup, "twitter:image") or _meta(soup, "twitter:image:src")
    if twitter_image:
        candidates.append(twitter_image)
    if not candidates:
        # Nothing structured named a photo at all - most small-business sites
        # never publish JSON-LD or a card image, so this is the common case,
        # not a rare one. Page furniture only now, never ahead of it.
        candidates.extend(_generic_image_srcs(soup))

    absolute: dict[str, None] = {}
    for candidate in candidates:
        # Relative image paths are common and useless to a downstream renderer,
        # so they are resolved against the URL we actually landed on.
        resolved = urljoin(base_url, candidate)
        if urlsplit(resolved).scheme in {"http", "https"}:
            absolute.setdefault(resolved, None)
    return tuple(absolute)[:MAX_PHOTOS]


def _generic_image_srcs(soup: BeautifulSoup) -> list[str]:
    found: list[str] = []
    for img in soup.find_all("img"):
        if not isinstance(img, Tag) or not _looks_like_a_photo(img):
            continue
        src = _img_src(img)
        if src is not None:
            found.append(src)
    return found


def _looks_like_a_photo(img: Tag) -> bool:
    src = _img_src(img)
    if src is not None and any(hint in src.lower() for hint in _ICON_SRC_HINTS):
        return False
    width, height = _int_attr(img, "width"), _int_attr(img, "height")
    if width is None or height is None:
        # Most real content photos declare no size at all; only a stated,
        # small size is evidence against a tag, not the absence of one.
        return True
    return width >= MIN_IMG_DIMENSION_PX and height >= MIN_IMG_DIMENSION_PX


def _img_src(img: Tag) -> str | None:
    for attr in _IMG_SRC_ATTRS:
        value = img.get(attr)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _int_attr(tag: Tag, name: str) -> int | None:
    value = tag.get(name)
    if not isinstance(value, str):
        return None
    try:
        return int(value)
    except ValueError:
        return None


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

"""Detecting a page that needs JavaScript to render.

Lives in ``infrastructure`` rather than ``domain`` because it parses real HTML
with BeautifulSoup - a third-party SDK the domain layer stays free of. A page
served without executing its scripts often reduces to a near-empty ``<div
id="root">``; measuring how little text survives once scripts and style are
stripped out is a cheap, framework-agnostic way to notice that.
"""

from __future__ import annotations

from typing import Final

from bs4 import BeautifulSoup

from makeover_discovery.domain.model.web import FetchedPage

PARSER: Final = "lxml"
MIN_VISIBLE_TEXT_CHARS: Final = 200
"""Below this, a page is treated as a JS shell.

Chosen well under a real short page's body copy (a one-line "we're closed for
renovation" notice is still meaningful) but well above what an empty React or
Vue root div renders to server-side."""

_NON_CONTENT_TAGS: Final = ("script", "style", "noscript", "template")


def visible_text_of(html: str) -> str:
    """Text a reader would actually see, collapsed to single spaces."""
    soup = BeautifulSoup(html, PARSER)
    for tag in soup(_NON_CONTENT_TAGS):
        tag.decompose()
    return " ".join(soup.get_text(separator=" ").split())


def looks_like_js_shell(page: FetchedPage) -> bool:
    """Whether ``page`` likely needs a real browser to render its content."""
    return len(visible_text_of(page.html)) < MIN_VISIBLE_TEXT_CHARS

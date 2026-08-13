"""Escalating from a plain fetch to a rendered one.

Composes two ``WebFetcher``s rather than being a third concrete fetcher, so
either side can be swapped without touching this logic - the primary could as
easily be a fixture-backed fetcher in a test.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Final

from makeover_discovery.application.ports.web_fetcher import WebFetcher
from makeover_discovery.domain.model.web import FetchedPage
from makeover_discovery.infrastructure.crawl.js_shell_heuristic import looks_like_js_shell

ShouldEscalate = Callable[[FetchedPage], bool]

DEFAULT_SHOULD_ESCALATE: Final[ShouldEscalate] = looks_like_js_shell


class FallbackWebFetcher:
    """Tries ``primary``; escalates to ``fallback`` only when the result looks
    like it did not actually contain the page's content.

    A dead link is left alone. A page that never loaded is not a page a
    browser will load differently, and paying for a browser boot on every
    fetch that failed outright would make enrichment far slower for no gain.
    """

    def __init__(
        self,
        primary: WebFetcher,
        fallback: WebFetcher,
        *,
        should_escalate: ShouldEscalate = DEFAULT_SHOULD_ESCALATE,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._should_escalate = should_escalate

    async def fetch(self, url: str) -> FetchedPage | None:
        page = await self._primary.fetch(url)
        if page is None or not self._should_escalate(page):
            return page

        rendered = await self._fallback.fetch(url)
        # Keep the unrendered shell rather than nothing: a thin server-rendered
        # page still beats an enrichment run that came back empty.
        return rendered if rendered is not None else page

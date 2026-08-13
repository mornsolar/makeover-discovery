"""Web fetching port."""

from __future__ import annotations

from typing import Protocol

from makeover_discovery.domain.model.web import FetchedPage


class WebFetcher(Protocol):
    """Retrieves a page.

    Returns ``None`` when the page is unavailable or not worth parsing - a dead
    business website is an ordinary finding, not an error worth aborting an
    enrichment run for.
    """

    async def fetch(self, url: str) -> FetchedPage | None: ...

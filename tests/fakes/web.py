"""Fakes for the enrichment ports."""

from __future__ import annotations

from datetime import UTC, datetime

from makeover_discovery.domain.errors import PolicyViolationError
from makeover_discovery.domain.model.web import ExtractedContent, FetchedPage

FETCHED_AT = datetime(2026, 8, 13, 9, 30, tzinfo=UTC)


def make_page(html: str = "<html></html>", url: str = "https://ali.example") -> FetchedPage:
    return FetchedPage(
        requested_url=url,
        final_url=url,
        status_code=200,
        html=html,
        fetched_at=FETCHED_AT,
    )


class FakeWebFetcher:
    """Returns a prepared page, recording what it was asked for."""

    def __init__(self, page: FetchedPage | None = None) -> None:
        self._page = page
        self.urls: list[str] = []

    async def fetch(self, url: str) -> FetchedPage | None:
        self.urls.append(url)
        return self._page


class ForbiddenWebFetcher:
    """Refuses everything, as a robots.txt disallow would."""

    async def fetch(self, url: str) -> FetchedPage | None:
        raise PolicyViolationError(f"robots.txt forbids fetching {url}")


class FakeExtractor:
    """Returns prepared content without parsing anything."""

    def __init__(self, content: ExtractedContent | None = None) -> None:
        self._content = content or ExtractedContent()

    def extract(self, page: FetchedPage) -> ExtractedContent:
        return self._content


class AllowAllRobots:
    async def is_allowed(self, url: str) -> bool:
        return True


class DenyAllRobots:
    async def is_allowed(self, url: str) -> bool:
        return False

"""Content extraction port."""

from __future__ import annotations

from typing import Protocol

from makeover_discovery.domain.model.web import ExtractedContent, FetchedPage


class ContentExtractor(Protocol):
    """Turns a fetched page into the few facts a design brief needs.

    Synchronous: parsing is CPU-bound and local, and pretending otherwise would
    put an await on a call that never yields.
    """

    def extract(self, page: FetchedPage) -> ExtractedContent: ...

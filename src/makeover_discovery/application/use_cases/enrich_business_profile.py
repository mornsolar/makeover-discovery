"""Turn a search hit into a fully sourced business profile."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from makeover_contracts.business import (
    MAX_DESCRIPTORS,
    MAX_PHOTOS,
    BusinessCandidate,
    BusinessProfile,
)
from makeover_contracts.provenance import DataLicense, DataSource, Provenanced, SourceRef

from makeover_discovery.application.ports.clock import Clock
from makeover_discovery.application.ports.content_extractor import ContentExtractor
from makeover_discovery.application.ports.web_fetcher import WebFetcher
from makeover_discovery.domain.errors import PolicyViolationError
from makeover_discovery.domain.model.slug import to_slug
from makeover_discovery.domain.model.web import ExtractedContent
from makeover_discovery.domain.policy.redaction import RedactionPolicy
from makeover_discovery.domain.policy.retention import RetentionPolicy


class WebsiteOutcome(StrEnum):
    """What happened when we tried the business's own site.

    Recorded rather than discarded: "we were forbidden" and "there was nothing
    there" lead to very different follow-up, and collapsing them into a silent
    empty profile hides which one occurred.
    """

    NOT_LISTED = "not_listed"
    FETCHED = "fetched"
    ROBOTS_DENIED = "robots_denied"
    UNAVAILABLE = "unavailable"
    EMPTY = "empty"


@dataclass(frozen=True)
class EnrichmentResult:
    profile: BusinessProfile
    website_outcome: WebsiteOutcome


class EnrichBusinessProfile:
    """Assembles a ``BusinessProfile`` from a candidate plus its own website.

    Every field it writes is wrapped in ``Provenanced``, so a value without a
    recorded source cannot be constructed here even by mistake.
    """

    def __init__(
        self,
        fetcher: WebFetcher,
        extractor: ContentExtractor,
        clock: Clock,
        *,
        retention: RetentionPolicy,
        redaction: RedactionPolicy,
    ) -> None:
        self._fetcher = fetcher
        self._extractor = extractor
        self._clock = clock
        self._retention = retention
        self._redaction = redaction

    async def execute(self, candidate: BusinessCandidate) -> EnrichmentResult:
        content, outcome = await self._read_website(candidate.website)
        profile = self._assemble(candidate, content)
        return EnrichmentResult(profile=profile, website_outcome=outcome)

    async def _read_website(
        self,
        website: str | None,
    ) -> tuple[ExtractedContent | None, WebsiteOutcome]:
        if website is None:
            return None, WebsiteOutcome.NOT_LISTED
        try:
            page = await self._fetcher.fetch(website)
        except PolicyViolationError:
            # Surfaced, not swallowed: the caller learns the site was off limits
            # rather than that it happened to have nothing on it.
            return None, WebsiteOutcome.ROBOTS_DENIED
        if page is None:
            return None, WebsiteOutcome.UNAVAILABLE

        content = self._extractor.extract(page)
        if content.is_empty:
            return None, WebsiteOutcome.EMPTY
        return content, WebsiteOutcome.FETCHED

    def _assemble(
        self,
        candidate: BusinessCandidate,
        content: ExtractedContent | None,
    ) -> BusinessProfile:
        directory = candidate.source
        web = self._website_source(candidate.website, directory.fetched_at)

        return BusinessProfile(
            id=to_slug(candidate.name, candidate.external_id),
            # The directory's name wins over the website's: it is the one the
            # search matched on, and swapping it would break the link back.
            name=Provenanced(value=candidate.name, source=directory),
            category=Provenanced(value=candidate.category, source=directory),
            location=Provenanced(value=candidate.location, source=directory),
            address_line=_maybe(candidate.address_line, directory),
            website=_maybe(candidate.website, directory),
            phone=_maybe(self._clean(content.phone if content else None), web),
            descriptors=self._descriptors(content, web),
            photo_urls=self._photos(content, web),
        )

    def _website_source(self, website: str | None, fetched_at: datetime) -> SourceRef:
        return self._retention.build_source_ref(
            source=DataSource.BUSINESS_WEBSITE,
            data_license=DataLicense.PUBLICLY_PUBLISHED,
            fetched_at=fetched_at,
            url=website,
        )

    def _clean(self, value: str | None) -> str | None:
        return self._redaction.clean(value) if value is not None else None

    def _descriptors(
        self,
        content: ExtractedContent | None,
        source: SourceRef,
    ) -> tuple[Provenanced[str], ...]:
        if content is None:
            return ()
        cleaned = self._redaction.clean_all(content.descriptors, MAX_DESCRIPTORS)
        return tuple(Provenanced(value=value, source=source) for value in cleaned)

    def _photos(
        self,
        content: ExtractedContent | None,
        source: SourceRef,
    ) -> tuple[Provenanced[str], ...]:
        if content is None:
            return ()
        return tuple(
            Provenanced(value=url, source=source) for url in content.photo_urls[:MAX_PHOTOS]
        )


def _maybe(value: str | None, source: SourceRef) -> Provenanced[str] | None:
    return Provenanced(value=value, source=source) if value is not None else None

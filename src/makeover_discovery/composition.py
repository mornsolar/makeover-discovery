"""Object graph construction.

The HTTP API and the CLI need the same adapters wired the same way, so the
wiring lives here once. Outside of tests, this is the only module that names
concrete adapter classes; everything else depends on the Protocols in
``application.ports``.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from makeover_discovery.application.ports.business_directory import BusinessDirectory
from makeover_discovery.application.ports.cache import ResponseCache
from makeover_discovery.application.ports.clock import Clock
from makeover_discovery.application.ports.rate_limiter import RateLimiter
from makeover_discovery.application.ports.web_fetcher import WebFetcher
from makeover_discovery.application.use_cases.discover_businesses import DiscoverBusinesses
from makeover_discovery.application.use_cases.enrich_business_profile import (
    EnrichBusinessProfile,
)
from makeover_discovery.config.settings import Settings
from makeover_discovery.domain.policy.redaction import RedactionPolicy
from makeover_discovery.domain.policy.retention import RetentionPolicy
from makeover_discovery.infrastructure.cache.memory import InMemoryTTLCache
from makeover_discovery.infrastructure.crawl.fallback_fetcher import FallbackWebFetcher
from makeover_discovery.infrastructure.crawl.httpx_fetcher import HttpxWebFetcher
from makeover_discovery.infrastructure.crawl.playwright_fetcher import PlaywrightWebFetcher
from makeover_discovery.infrastructure.crawl.robots import RobotsGate
from makeover_discovery.infrastructure.directory import overpass
from makeover_discovery.infrastructure.directory.google_places import RATE_KEY as PLACES_RATE_KEY
from makeover_discovery.infrastructure.directory.google_places import GooglePlacesDirectory
from makeover_discovery.infrastructure.directory.overpass import OverpassDirectory
from makeover_discovery.infrastructure.extract.html_extractor import HtmlContentExtractor
from makeover_discovery.infrastructure.geocoding import nominatim
from makeover_discovery.infrastructure.geocoding.nominatim import NominatimGeocoder
from makeover_discovery.infrastructure.http.cached_client import CachedHttpClient
from makeover_discovery.infrastructure.ratelimit.per_key import PerKeyRateLimiter


@dataclass(frozen=True)
class SharedResources:
    """Objects that must outlive a single request.

    The rate limiter in particular is worthless per-request: it only enforces a
    gap between calls if every call consults the same instance.
    """

    http_client: httpx.AsyncClient
    rate_limiter: RateLimiter
    cache: ResponseCache

    async def aclose(self) -> None:
        await self.http_client.aclose()


def create_shared_resources(settings: Settings) -> SharedResources:
    return SharedResources(
        http_client=httpx.AsyncClient(timeout=settings.http_timeout_s, follow_redirects=True),
        rate_limiter=PerKeyRateLimiter(
            # Any host we have no specific policy for - every business site -
            # gets the crawl default.
            default_interval_s=settings.crawl_min_interval_s,
            intervals={
                nominatim.RATE_KEY: settings.nominatim_min_interval_s,
                overpass.RATE_KEY: settings.overpass_min_interval_s,
                PLACES_RATE_KEY: settings.google_places_min_interval_s,
            },
        ),
        cache=InMemoryTTLCache(max_entries=settings.cache_max_entries),
    )


def build_discover_businesses(
    settings: Settings,
    resources: SharedResources,
    clock: Clock,
) -> DiscoverBusinesses:
    http = CachedHttpClient(
        resources.http_client,
        rate_limiter=resources.rate_limiter,
        cache=resources.cache,
        user_agent=settings.user_agent,
        cache_ttl_s=settings.cache_ttl_s,
    )
    return DiscoverBusinesses(
        geocoder=NominatimGeocoder(
            http,
            base_url=settings.nominatim_base_url,
            default_radius_m=settings.default_search_radius_m,
            max_radius_m=settings.max_search_radius_m,
        ),
        directory=_build_directory(settings, http, clock),
    )


def _build_directory(
    settings: Settings,
    http: CachedHttpClient,
    clock: Clock,
) -> BusinessDirectory:
    # OpenStreetMap is the primary, no-key source. Places only takes over when
    # an operator has both opted in and supplied a key; Settings itself refuses
    # to boot with the flag on and no key, so reaching here with the flag on
    # means the key is present.
    if settings.google_places_enabled:
        assert settings.google_places_api_key is not None  # enforced by Settings at boot
        return GooglePlacesDirectory(
            http,
            clock,
            base_url=settings.google_places_base_url,
            api_key=settings.google_places_api_key.get_secret_value(),
            retention=RetentionPolicy(),
        )
    return OverpassDirectory(
        http,
        clock,
        base_url=settings.overpass_base_url,
        retention=RetentionPolicy(),
    )


def build_enrich_business_profile(
    settings: Settings,
    resources: SharedResources,
    clock: Clock,
) -> EnrichBusinessProfile:
    robots = RobotsGate(
        resources.http_client,
        rate_limiter=resources.rate_limiter,
        cache=resources.cache,
        user_agent=settings.user_agent,
        cache_ttl_s=settings.robots_cache_ttl_s,
    )
    return EnrichBusinessProfile(
        fetcher=_build_fetcher(settings, resources, robots, clock),
        extractor=HtmlContentExtractor(),
        clock=clock,
        retention=RetentionPolicy(),
        redaction=RedactionPolicy(),
    )


def _build_fetcher(
    settings: Settings,
    resources: SharedResources,
    robots: RobotsGate,
    clock: Clock,
) -> WebFetcher:
    httpx_fetcher = HttpxWebFetcher(
        resources.http_client,
        robots,
        clock,
        rate_limiter=resources.rate_limiter,
        user_agent=settings.user_agent,
    )
    if not settings.use_playwright_fallback:
        return httpx_fetcher

    playwright_fetcher = PlaywrightWebFetcher(
        robots,
        clock,
        rate_limiter=resources.rate_limiter,
        user_agent=settings.user_agent,
        navigation_timeout_ms=settings.playwright_navigation_timeout_ms,
    )
    # httpx first: most business sites are server-rendered, and a browser boot
    # costs roughly two orders of magnitude more than a plain HTTP request.
    return FallbackWebFetcher(httpx_fetcher, playwright_fetcher)

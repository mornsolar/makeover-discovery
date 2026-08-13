"""Object graph construction.

The HTTP API and the CLI need the same adapters wired the same way, so the
wiring lives here once. Outside of tests, this is the only module that names
concrete adapter classes; everything else depends on the Protocols in
``application.ports``.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from makeover_discovery.application.ports.cache import ResponseCache
from makeover_discovery.application.ports.clock import Clock
from makeover_discovery.application.ports.rate_limiter import RateLimiter
from makeover_discovery.application.use_cases.discover_businesses import DiscoverBusinesses
from makeover_discovery.config.settings import Settings
from makeover_discovery.infrastructure.cache.memory import InMemoryTTLCache
from makeover_discovery.infrastructure.directory import overpass
from makeover_discovery.infrastructure.directory.overpass import OverpassDirectory
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
            default_interval_s=settings.nominatim_min_interval_s,
            intervals={
                nominatim.RATE_KEY: settings.nominatim_min_interval_s,
                overpass.RATE_KEY: settings.overpass_min_interval_s,
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
        directory=OverpassDirectory(http, clock, base_url=settings.overpass_base_url),
    )

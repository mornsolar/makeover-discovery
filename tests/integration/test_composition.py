"""Object graph wiring decisions.

Only the branching logic is asserted here - which concrete class a flag
selects - not the adapters themselves, which have their own test suites.
"""

from __future__ import annotations

import httpx

from makeover_discovery.application.ports.rate_limiter import RateLimiter
from makeover_discovery.composition import SharedResources, _build_directory, _build_fetcher
from makeover_discovery.config.settings import Settings
from makeover_discovery.infrastructure.cache.memory import InMemoryTTLCache
from makeover_discovery.infrastructure.crawl.fallback_fetcher import FallbackWebFetcher
from makeover_discovery.infrastructure.crawl.httpx_fetcher import HttpxWebFetcher
from makeover_discovery.infrastructure.crawl.robots import RobotsGate
from makeover_discovery.infrastructure.directory.google_places import GooglePlacesDirectory
from makeover_discovery.infrastructure.directory.overpass import OverpassDirectory
from makeover_discovery.infrastructure.http.cached_client import CachedHttpClient
from tests.fakes.clock import FixedClock
from tests.integration.conftest import TEST_USER_AGENT


def make_settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, **overrides)


def resources_for(http_client: httpx.AsyncClient, rate_limiter: RateLimiter) -> SharedResources:
    return SharedResources(
        http_client=http_client, rate_limiter=rate_limiter, cache=InMemoryTTLCache()
    )


def robots_for(http_client: httpx.AsyncClient, rate_limiter: RateLimiter) -> RobotsGate:
    return RobotsGate(
        http_client,
        rate_limiter=rate_limiter,
        cache=InMemoryTTLCache(),
        user_agent=TEST_USER_AGENT,
        cache_ttl_s=60.0,
    )


def test_uses_overpass_by_default(cached_http: CachedHttpClient):
    directory = _build_directory(make_settings(), cached_http, FixedClock())

    assert isinstance(directory, OverpassDirectory)


def test_switches_to_places_once_enabled_with_a_key(cached_http: CachedHttpClient):
    directory = _build_directory(
        make_settings(google_places_enabled=True, google_places_api_key="k"),
        cached_http,
        FixedClock(),
    )

    assert isinstance(directory, GooglePlacesDirectory)


def test_uses_plain_httpx_by_default(http_client: httpx.AsyncClient, rate_limiter: RateLimiter):
    fetcher = _build_fetcher(
        make_settings(),
        resources_for(http_client, rate_limiter),
        robots_for(http_client, rate_limiter),
        FixedClock(),
    )

    assert isinstance(fetcher, HttpxWebFetcher)


def test_wraps_httpx_with_a_playwright_fallback_when_enabled(
    http_client: httpx.AsyncClient, rate_limiter: RateLimiter
):
    fetcher = _build_fetcher(
        make_settings(use_playwright_fallback=True),
        resources_for(http_client, rate_limiter),
        robots_for(http_client, rate_limiter),
        FixedClock(),
    )

    assert isinstance(fetcher, FallbackWebFetcher)

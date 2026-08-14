"""Object graph wiring decisions.

Only the branching logic is asserted here - which concrete class a flag
selects - not the adapters themselves, which have their own test suites.
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from makeover_discovery.application.ports.rate_limiter import RateLimiter
from makeover_discovery.application.use_cases.generate_design_brief import GenerateDesignBrief
from makeover_discovery.application.use_cases.run_makeover_pipeline import RunMakeoverPipeline
from makeover_discovery.composition import (
    SharedResources,
    _build_capability_source,
    _build_directory,
    _build_fetcher,
    build_generate_design_brief,
    build_run_makeover_pipeline,
)
from makeover_discovery.config.settings import Settings
from makeover_discovery.domain.errors import ConfigurationError
from makeover_discovery.infrastructure.cache.memory import InMemoryTTLCache
from makeover_discovery.infrastructure.capabilities.http_capability_source import (
    HttpCapabilitySource,
)
from makeover_discovery.infrastructure.capabilities.static_manifest import StaticCapabilitySource
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
        http_client=http_client,
        rate_limiter=rate_limiter,
        cache=InMemoryTTLCache(),
        db_engine=create_async_engine("sqlite+aiosqlite://"),
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


def test_uses_the_builtin_manifest_until_a_render_service_is_configured(
    http_client: httpx.AsyncClient, rate_limiter: RateLimiter
):
    source = _build_capability_source(make_settings(), resources_for(http_client, rate_limiter))

    assert isinstance(source, StaticCapabilitySource)


def test_asks_the_render_service_once_it_has_a_url(
    http_client: httpx.AsyncClient, rate_limiter: RateLimiter
):
    source = _build_capability_source(
        make_settings(render_service_url="https://render.test"),
        resources_for(http_client, rate_limiter),
    )

    assert isinstance(source, HttpCapabilitySource)


def test_refuses_to_build_the_brief_use_case_without_a_key(
    http_client: httpx.AsyncClient, rate_limiter: RateLimiter
):
    # Configuration is checked where the capability is wired, not on the first
    # request that happens to need it.
    with pytest.raises(ConfigurationError, match="MAKEOVER_ANTHROPIC_API_KEY"):
        build_generate_design_brief(
            make_settings(), resources_for(http_client, rate_limiter), FixedClock()
        )


def test_builds_the_brief_use_case_when_a_key_is_present(
    http_client: httpx.AsyncClient, rate_limiter: RateLimiter
):
    use_case = build_generate_design_brief(
        make_settings(anthropic_api_key="sk-test"),
        resources_for(http_client, rate_limiter),
        FixedClock(),
    )

    assert isinstance(use_case, GenerateDesignBrief)


def test_refuses_to_build_the_pipeline_without_a_render_service_url(
    http_client: httpx.AsyncClient, rate_limiter: RateLimiter
):
    # There is nothing to submit a job to yet - checked at wiring time, same
    # as the Anthropic-key guard above.
    with pytest.raises(ConfigurationError, match="MAKEOVER_RENDER_SERVICE_URL"):
        build_run_makeover_pipeline(
            make_settings(anthropic_api_key="sk-test"),
            resources_for(http_client, rate_limiter),
            FixedClock(),
        )


def test_builds_the_pipeline_when_a_render_service_url_is_present(
    http_client: httpx.AsyncClient, rate_limiter: RateLimiter
):
    use_case = build_run_makeover_pipeline(
        make_settings(anthropic_api_key="sk-test", render_service_url="https://render.test"),
        resources_for(http_client, rate_limiter),
        FixedClock(),
    )

    assert isinstance(use_case, RunMakeoverPipeline)

"""Object graph construction.

The HTTP API and the CLI need the same adapters wired the same way, so the
wiring lives here once. Outside of tests, this is the only module that names
concrete adapter classes; everything else depends on the Protocols in
``application.ports``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from anthropic import AsyncAnthropic
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from makeover_discovery.application.ports.artifact_store import ArtifactStore
from makeover_discovery.application.ports.business_directory import BusinessDirectory
from makeover_discovery.application.ports.cache import ResponseCache
from makeover_discovery.application.ports.capability_source import CapabilitySource
from makeover_discovery.application.ports.clock import Clock
from makeover_discovery.application.ports.landing_page_builder import LandingPageBuilder
from makeover_discovery.application.ports.project_repository import ProjectRepository
from makeover_discovery.application.ports.rate_limiter import RateLimiter
from makeover_discovery.application.ports.web_fetcher import WebFetcher
from makeover_discovery.application.use_cases.compose_scene_spec import ComposeSceneSpec
from makeover_discovery.application.use_cases.discover_businesses import DiscoverBusinesses
from makeover_discovery.application.use_cases.enrich_business_profile import (
    EnrichBusinessProfile,
)
from makeover_discovery.application.use_cases.generate_design_brief import GenerateDesignBrief
from makeover_discovery.application.use_cases.publish_project import PublishProject
from makeover_discovery.application.use_cases.run_makeover_pipeline import RunMakeoverPipeline
from makeover_discovery.application.use_cases.save_project import SaveProject
from makeover_discovery.application.use_cases.takedown_project import TakedownProject
from makeover_discovery.application.use_cases.upload_before_image import UploadBeforeImage
from makeover_discovery.config.settings import Settings
from makeover_discovery.domain.errors import ConfigurationError
from makeover_discovery.domain.policy.redaction import RedactionPolicy
from makeover_discovery.domain.policy.retention import RetentionPolicy
from makeover_discovery.infrastructure.cache.memory import InMemoryTTLCache
from makeover_discovery.infrastructure.capabilities.http_capability_source import (
    HttpCapabilitySource,
)
from makeover_discovery.infrastructure.capabilities.static_manifest import StaticCapabilitySource
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
from makeover_discovery.infrastructure.landing.jinja_landing_builder import (
    JinjaLandingPageBuilder,
)
from makeover_discovery.infrastructure.llm.anthropic_brief_generator import (
    AnthropicBriefGenerator,
)
from makeover_discovery.infrastructure.llm.pricing import pricing_for
from makeover_discovery.infrastructure.persistence.engine import create_db_engine
from makeover_discovery.infrastructure.persistence.sqlalchemy_project_repository import (
    SqlAlchemyProjectRepository,
)
from makeover_discovery.infrastructure.ratelimit.per_key import PerKeyRateLimiter
from makeover_discovery.infrastructure.render.http_render_client import HttpRenderClient
from makeover_discovery.infrastructure.storage.local_fs import LocalFsArtifactStore


@dataclass(frozen=True)
class SharedResources:
    """Objects that must outlive a single request.

    The rate limiter in particular is worthless per-request: it only enforces a
    gap between calls if every call consults the same instance.
    """

    http_client: httpx.AsyncClient
    rate_limiter: RateLimiter
    cache: ResponseCache
    db_engine: AsyncEngine

    async def aclose(self) -> None:
        await self.http_client.aclose()
        await self.db_engine.dispose()


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
        db_engine=create_db_engine(settings.database_url),
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


def build_generate_design_brief(
    settings: Settings,
    resources: SharedResources,
    clock: Clock,
) -> GenerateDesignBrief:
    if settings.anthropic_api_key is None:
        raise ConfigurationError("MAKEOVER_ANTHROPIC_API_KEY must be set to generate design briefs")
    client = AsyncAnthropic(api_key=settings.anthropic_api_key.get_secret_value())

    async def create(**kwargs: Any) -> Any:
        # A thin wrapper rather than the bound method: the SDK's ``create`` is
        # overloaded on ``stream``, which no structural type can match.
        return await client.messages.create(**kwargs)

    return GenerateDesignBrief(
        generator=AnthropicBriefGenerator(
            create,
            clock,
            model=settings.anthropic_model,
            max_tokens=settings.anthropic_max_tokens,
            effort=settings.anthropic_effort,
        ),
        capabilities=_build_capability_source(settings, resources),
        pricing=pricing_for(settings.anthropic_model),
        max_repair_attempts=settings.brief_max_repair_attempts,
    )


def _build_capability_source(settings: Settings, resources: SharedResources) -> CapabilitySource:
    # No render service configured is the normal state until Phase 5: fall back
    # to the vocabulary compiled into this build rather than refusing to run.
    if settings.render_service_url is None:
        return StaticCapabilitySource()
    return HttpCapabilitySource(
        CachedHttpClient(
            resources.http_client,
            rate_limiter=resources.rate_limiter,
            cache=resources.cache,
            user_agent=settings.user_agent,
            cache_ttl_s=settings.capabilities_cache_ttl_s,
        ),
        base_url=settings.render_service_url,
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


def build_run_makeover_pipeline(
    settings: Settings,
    resources: SharedResources,
    clock: Clock,
) -> RunMakeoverPipeline:
    if settings.render_service_url is None:
        # Nothing to submit a job to yet - the same guard shape as the
        # Anthropic-key check in build_generate_design_brief.
        raise ConfigurationError(
            "MAKEOVER_RENDER_SERVICE_URL must be set to run the makeover pipeline"
        )
    return RunMakeoverPipeline(
        discover=build_discover_businesses(settings, resources, clock),
        enrich=build_enrich_business_profile(settings, resources, clock),
        brief=build_generate_design_brief(settings, resources, clock),
        compose=ComposeSceneSpec(),
        capabilities=_build_capability_source(settings, resources),
        render=HttpRenderClient(
            resources.http_client,
            base_url=settings.render_service_url,
            user_agent=settings.user_agent,
        ),
        poll_interval_s=settings.render_poll_interval_s,
        poll_timeout_s=settings.render_poll_timeout_s,
    )


def build_project_repository(resources: SharedResources) -> ProjectRepository:
    session_factory = async_sessionmaker(resources.db_engine, expire_on_commit=False)
    return SqlAlchemyProjectRepository(session_factory)


def _build_artifact_store(settings: Settings) -> ArtifactStore:
    return LocalFsArtifactStore(settings.artifact_store_root)


def build_save_project(settings: Settings, resources: SharedResources, clock: Clock) -> SaveProject:
    return SaveProject(build_project_repository(resources), _build_artifact_store(settings), clock)


def build_upload_before_image(settings: Settings, resources: SharedResources) -> UploadBeforeImage:
    return UploadBeforeImage(build_project_repository(resources), _build_artifact_store(settings))


def build_publish_project(resources: SharedResources) -> PublishProject:
    return PublishProject(build_project_repository(resources))


def build_takedown_project(resources: SharedResources) -> TakedownProject:
    return TakedownProject(build_project_repository(resources))


def build_landing_page_builder() -> LandingPageBuilder:
    return JinjaLandingPageBuilder()

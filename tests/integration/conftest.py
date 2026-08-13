"""Shared wiring for adapter-level tests."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest

from makeover_discovery.application.ports.rate_limiter import RateLimiter
from makeover_discovery.infrastructure.cache.memory import InMemoryTTLCache
from makeover_discovery.infrastructure.http.cached_client import CachedHttpClient
from tests.fakes.rate_limiter import RecordingRateLimiter

TEST_USER_AGENT = "makeover-discovery-tests/0.1 (+mailto:tests@example.invalid)"
CACHE_TTL_S = 300.0


@pytest.fixture
async def http_client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient() as client:
        yield client


@pytest.fixture
def rate_limiter() -> RecordingRateLimiter:
    return RecordingRateLimiter()


@pytest.fixture
def cached_http(http_client: httpx.AsyncClient, rate_limiter: RateLimiter) -> CachedHttpClient:
    return CachedHttpClient(
        http_client,
        rate_limiter=rate_limiter,
        cache=InMemoryTTLCache(),
        user_agent=TEST_USER_AGENT,
        cache_ttl_s=CACHE_TTL_S,
    )

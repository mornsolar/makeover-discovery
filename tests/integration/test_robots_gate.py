"""robots.txt enforcement."""

from __future__ import annotations

import httpx
import pytest
import respx

from makeover_discovery.infrastructure.cache.memory import InMemoryTTLCache
from makeover_discovery.infrastructure.crawl.robots import RobotsGate, host_of
from tests.integration.conftest import CACHE_TTL_S, TEST_USER_AGENT

BASE_URL = "https://ali.example"
PAGE_URL = f"{BASE_URL}/menu"
DISALLOW_ALL = "User-agent: *\nDisallow: /"
ALLOW_WITH_EXCEPTION = "User-agent: *\nDisallow: /private/"


@pytest.fixture
def gate(http_client, rate_limiter) -> RobotsGate:
    return RobotsGate(
        http_client,
        rate_limiter=rate_limiter,
        cache=InMemoryTTLCache(),
        user_agent=TEST_USER_AGENT,
        cache_ttl_s=CACHE_TTL_S,
    )


async def serve(body: str = "", status: int = 200) -> respx.MockRouter:
    mock = respx.mock(base_url=BASE_URL)
    mock.get("/robots.txt").mock(return_value=httpx.Response(status, text=body))
    return mock


async def test_permits_a_path_no_rule_covers(gate):
    with await serve(ALLOW_WITH_EXCEPTION):
        assert await gate.is_allowed(PAGE_URL) is True


async def test_refuses_a_disallowed_path(gate):
    with await serve(ALLOW_WITH_EXCEPTION):
        assert await gate.is_allowed(f"{BASE_URL}/private/rates") is False


async def test_refuses_everything_under_a_blanket_disallow(gate):
    with await serve(DISALLOW_ALL):
        assert await gate.is_allowed(PAGE_URL) is False


async def test_permits_everything_when_no_robots_file_exists(gate):
    # A 404 means the host published no rules, which permits everything.
    with await serve("Not found", status=404):
        assert await gate.is_allowed(PAGE_URL) is True


async def test_refuses_everything_when_robots_cannot_be_read(gate):
    # RFC 9309 asks crawlers to treat an unreachable robots.txt as a full
    # disallow; guessing the other way would crawl a site that forbade it.
    with await serve("Server error", status=503):
        assert await gate.is_allowed(PAGE_URL) is False


async def test_refuses_everything_when_access_to_robots_is_denied(gate):
    with await serve("Forbidden", status=403):
        assert await gate.is_allowed(PAGE_URL) is False


async def test_refuses_everything_when_the_host_is_unreachable(gate):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/robots.txt").mock(side_effect=httpx.ConnectError("no route"))

        assert await gate.is_allowed(PAGE_URL) is False


async def test_reads_robots_once_per_host(gate):
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/robots.txt").mock(return_value=httpx.Response(200, text=""))

        await gate.is_allowed(PAGE_URL)
        await gate.is_allowed(f"{BASE_URL}/about")

    assert route.call_count == 1


async def test_throttles_the_host_before_reading_robots(gate, rate_limiter):
    with await serve(""):
        await gate.is_allowed(PAGE_URL)

    assert rate_limiter.keys == ["ali.example"]


async def test_refuses_a_url_that_is_not_http(gate):
    # Refusing is both safe and honest: we never checked a permission we cannot
    # act on anyway.
    assert await gate.is_allowed("ftp://ali.example/menu") is False


def test_reports_the_host_used_as_the_rate_limit_key():
    assert host_of(PAGE_URL) == "ali.example"
    assert host_of("not a url") is None

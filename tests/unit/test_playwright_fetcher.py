"""JavaScript-rendered page fetching, via an injected fake browser launcher."""

from __future__ import annotations

import pytest
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from makeover_discovery.domain.errors import PolicyViolationError
from makeover_discovery.infrastructure.crawl.playwright_fetcher import PlaywrightWebFetcher
from tests.fakes.clock import FixedClock
from tests.fakes.playwright import FakePage, FakeResponse, launcher_for
from tests.fakes.rate_limiter import RecordingRateLimiter
from tests.fakes.web import AllowAllRobots, DenyAllRobots

URL = "https://ali.example/menu"
USER_AGENT = "makeover-discovery-tests/0.1"


def build(page: FakePage, robots=None, rate_limiter=None):
    launch, browser = launcher_for(page)
    fetcher = PlaywrightWebFetcher(
        robots or AllowAllRobots(),
        FixedClock(),
        rate_limiter=rate_limiter or RecordingRateLimiter(),
        user_agent=USER_AGENT,
        launch=launch,
    )
    return fetcher, browser


async def test_returns_the_rendered_page():
    fetcher, _ = build(FakePage(html="<html><body>Kedai Kopi Ali</body></html>"))

    page = await fetcher.fetch(URL)

    assert page is not None
    assert page.html == "<html><body>Kedai Kopi Ali</body></html>"
    assert page.fetched_at == FixedClock().now()


async def test_uses_the_url_playwright_landed_on(fetch=None):
    fetcher, _ = build(FakePage(url="https://ali.example/menu?utm=1"))

    page = await fetcher.fetch(URL)

    assert page is not None
    assert page.final_url == "https://ali.example/menu?utm=1"


async def test_passes_the_configured_user_agent_to_the_browser_context():
    fetcher, browser = build(FakePage())

    await fetcher.fetch(URL)

    assert browser.user_agents == [USER_AGENT]


async def test_closes_the_context_after_fetching():
    fetcher, browser = build(FakePage())

    await fetcher.fetch(URL)

    assert browser.contexts[0].closed is True


async def test_returns_nothing_when_navigation_times_out():
    fetcher, _ = build(FakePage(goto_error=PlaywrightTimeoutError("timed out")))

    assert await fetcher.fetch(URL) is None


async def test_closes_the_context_even_after_a_timeout():
    fetcher, browser = build(FakePage(goto_error=PlaywrightTimeoutError("timed out")))

    await fetcher.fetch(URL)

    assert browser.contexts[0].closed is True


async def test_returns_nothing_for_a_failed_navigation():
    fetcher, _ = build(FakePage(response=FakeResponse(ok=False, status=500)))

    assert await fetcher.fetch(URL) is None


async def test_returns_nothing_when_playwright_reports_no_response():
    fetcher, _ = build(FakePage(response=None))

    assert await fetcher.fetch(URL) is None


async def test_refuses_a_page_robots_disallows():
    fetcher, _ = build(FakePage(), robots=DenyAllRobots())

    with pytest.raises(PolicyViolationError):
        await fetcher.fetch(URL)


async def test_does_not_launch_a_browser_for_a_page_robots_disallows():
    fetcher, browser = build(FakePage(), robots=DenyAllRobots())

    with pytest.raises(PolicyViolationError):
        await fetcher.fetch(URL)

    assert browser.contexts == []


async def test_throttles_per_host():
    rate_limiter = RecordingRateLimiter()
    fetcher, _ = build(FakePage(), rate_limiter=rate_limiter)

    await fetcher.fetch(URL)

    assert rate_limiter.keys == ["ali.example"]


async def test_refuses_a_url_that_is_not_http():
    fetcher, _ = build(FakePage())

    with pytest.raises(PolicyViolationError):
        await fetcher.fetch("ftp://ali.example/menu")

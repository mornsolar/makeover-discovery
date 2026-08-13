"""JavaScript-rendered page fetcher.

Reserved for sites the plain HTTP fetcher cannot read. Most small-business
sites are server-rendered and never reach this adapter; a browser boot costs
roughly two orders of magnitude more than an HTTP request, which is why it is
only ever invoked through ``FallbackWebFetcher`` rather than by default.

The browser launcher is injectable so the adapter's own logic - robots
enforcement, rate limiting, timeout handling, response mapping - can be unit
tested without a real Chromium binary, which this repo's toolchain does not
install by default (see the README for the one-time ``playwright install``).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Final

from playwright.async_api import Browser, async_playwright
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from makeover_discovery.application.ports.clock import Clock
from makeover_discovery.application.ports.rate_limiter import RateLimiter
from makeover_discovery.application.ports.robots import RobotsPolicy
from makeover_discovery.domain.errors import PolicyViolationError
from makeover_discovery.domain.model.web import MAX_HTML_BYTES, FetchedPage
from makeover_discovery.infrastructure.crawl.robots import host_of

DEFAULT_NAVIGATION_TIMEOUT_MS: Final = 15_000

BrowserLauncher = Callable[[], AbstractAsyncContextManager[Browser]]


@asynccontextmanager
async def _launch_chromium() -> AsyncIterator[Browser]:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            yield browser
        finally:
            await browser.close()


class PlaywrightWebFetcher:
    """Fetches a page by actually running its JavaScript.

    Checks robots.txt and throttles itself independently of any other
    fetcher, so it stays correct even when used on its own rather than behind
    ``FallbackWebFetcher``.
    """

    def __init__(
        self,
        robots: RobotsPolicy,
        clock: Clock,
        *,
        rate_limiter: RateLimiter,
        user_agent: str,
        navigation_timeout_ms: float = DEFAULT_NAVIGATION_TIMEOUT_MS,
        launch: BrowserLauncher | None = None,
    ) -> None:
        self._robots = robots
        self._clock = clock
        self._rate_limiter = rate_limiter
        self._user_agent = user_agent
        self._navigation_timeout_ms = navigation_timeout_ms
        self._launch = launch or _launch_chromium

    async def fetch(self, url: str) -> FetchedPage | None:
        if not await self._robots.is_allowed(url):
            raise PolicyViolationError(f"robots.txt forbids fetching {url}")

        host = host_of(url)
        if host is None:
            raise PolicyViolationError(f"{url} is not an http(s) URL")
        await self._rate_limiter.acquire(host)

        async with self._launch() as browser:
            return await self._render(browser, url)

    async def _render(self, browser: Browser, url: str) -> FetchedPage | None:
        context = await browser.new_context(user_agent=self._user_agent)
        try:
            page = await context.new_page()
            try:
                response = await page.goto(
                    url, wait_until="networkidle", timeout=self._navigation_timeout_ms
                )
            except PlaywrightTimeoutError:
                # A page that never settles is not one we can read reliably;
                # treated the same as any other unreachable page.
                return None
            if response is None or not response.ok:
                return None

            html = await page.content()
            if len(html.encode()) > MAX_HTML_BYTES:
                return None

            return FetchedPage(
                requested_url=url,
                final_url=page.url,
                status_code=response.status,
                html=html,
                fetched_at=self._clock.now(),
            )
        finally:
            await context.close()

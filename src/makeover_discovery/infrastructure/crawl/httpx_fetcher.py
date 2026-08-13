"""Plain HTTP page fetcher.

The default fetcher. Most small-business sites are server-rendered, so paying
for a browser on every fetch would be waste; the Playwright fetcher exists for
the ones that are not.

The robots check lives *inside* the fetcher rather than beside it. A gate the
caller has to remember to call is a gate that eventually goes uncalled.
"""

from __future__ import annotations

from typing import Final

import httpx

from makeover_discovery.application.ports.clock import Clock
from makeover_discovery.application.ports.rate_limiter import RateLimiter
from makeover_discovery.application.ports.robots import RobotsPolicy
from makeover_discovery.domain.errors import PolicyViolationError
from makeover_discovery.domain.model.web import MAX_HTML_BYTES, FetchedPage
from makeover_discovery.infrastructure.crawl.robots import host_of

HTML_CONTENT_TYPES: Final = ("text/html", "application/xhtml+xml")


class HttpxWebFetcher:
    """Fetches a page over HTTP, subject to robots.txt and a per-host rate limit."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        robots: RobotsPolicy,
        clock: Clock,
        *,
        rate_limiter: RateLimiter,
        user_agent: str,
    ) -> None:
        self._client = client
        self._robots = robots
        self._clock = clock
        self._rate_limiter = rate_limiter
        self._user_agent = user_agent

    async def fetch(self, url: str) -> FetchedPage | None:
        if not await self._robots.is_allowed(url):
            raise PolicyViolationError(f"robots.txt forbids fetching {url}")

        host = host_of(url)
        if host is None:
            raise PolicyViolationError(f"{url} is not an http(s) URL")
        await self._rate_limiter.acquire(host)

        try:
            response = await self._client.get(
                url,
                headers={"User-Agent": self._user_agent, "Accept": "text/html"},
                follow_redirects=True,
            )
        except httpx.HTTPError:
            # A business website that no longer resolves is an ordinary finding.
            return None

        if not _is_usable(response):
            return None

        return FetchedPage(
            requested_url=url,
            final_url=str(response.url),
            status_code=response.status_code,
            html=response.text,
            fetched_at=self._clock.now(),
        )


def _is_usable(response: httpx.Response) -> bool:
    if response.status_code != httpx.codes.OK:
        return False
    content_type = response.headers.get("content-type", "").lower()
    if not content_type.startswith(HTML_CONTENT_TYPES):
        return False
    # Guards memory before the body is decoded to text, which for a hostile
    # response is the expensive step.
    return len(response.content) <= MAX_HTML_BYTES

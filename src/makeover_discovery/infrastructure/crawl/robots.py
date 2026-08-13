"""robots.txt enforcement.

Deliberately not built on ``CachedHttpClient``: robots has error semantics that
do not fit "raise on anything that is not 2xx". A 404 means the host published
no rules and everything is permitted, while a 5xx means we cannot know and must
assume nothing is - the opposite conclusions from two failure statuses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from makeover_discovery.application.ports.cache import ResponseCache
from makeover_discovery.application.ports.rate_limiter import RateLimiter

ROBOTS_PATH: Final = "/robots.txt"
CACHE_PREFIX: Final = "robots:"
MAX_ROBOTS_BYTES: Final = 512_000

ALLOW_ALL: Final = ""
"""Body standing in for "no rules published", which permits everything."""

DENY_ALL: Final = "User-agent: *\nDisallow: /"
"""Body standing in for "we could not find out", which permits nothing.

RFC 9309 asks crawlers to treat an unreachable robots.txt as a full disallow.
Guessing the other way would mean crawling a site that may have forbidden it.
"""


@dataclass(frozen=True)
class _Origin:
    scheme: str
    netloc: str

    @property
    def robots_url(self) -> str:
        return f"{self.scheme}://{self.netloc}{ROBOTS_PATH}"


def _origin_of(url: str) -> _Origin | None:
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return None
    return _Origin(scheme=parts.scheme, netloc=parts.netloc)


def host_of(url: str) -> str | None:
    """The host a URL belongs to, used as the per-domain rate-limit key."""
    origin = _origin_of(url)
    return origin.netloc if origin is not None else None


class RobotsGate:
    """Fetches, caches, and applies each host's robots.txt."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        rate_limiter: RateLimiter,
        cache: ResponseCache,
        user_agent: str,
        cache_ttl_s: float,
    ) -> None:
        self._client = client
        self._rate_limiter = rate_limiter
        self._cache = cache
        self._user_agent = user_agent
        self._cache_ttl_s = cache_ttl_s

    async def is_allowed(self, url: str) -> bool:
        origin = _origin_of(url)
        if origin is None:
            # Not something we could fetch anyway; refusing is both safe and
            # honest, rather than reporting a permission we never checked.
            return False

        parser = RobotFileParser()
        parser.parse((await self._body_for(origin)).splitlines())
        return parser.can_fetch(self._user_agent, url)

    async def _body_for(self, origin: _Origin) -> str:
        key = f"{CACHE_PREFIX}{origin.netloc}"
        cached = await self._cache.get(key)
        if cached is not None:
            return cached

        await self._rate_limiter.acquire(origin.netloc)
        body = await self._download(origin)
        await self._cache.set(key, body, self._cache_ttl_s)
        return body

    async def _download(self, origin: _Origin) -> str:
        try:
            response = await self._client.get(
                origin.robots_url,
                headers={"User-Agent": self._user_agent},
            )
        except httpx.HTTPError:
            return DENY_ALL

        if response.status_code == httpx.codes.NOT_FOUND:
            return ALLOW_ALL
        if response.status_code >= httpx.codes.BAD_REQUEST:
            # Includes 401/403, which RFC 9309 treats as "the whole site is
            # off limits", not merely "robots.txt is off limits".
            return DENY_ALL
        if len(response.content) > MAX_ROBOTS_BYTES:
            return DENY_ALL
        return response.text

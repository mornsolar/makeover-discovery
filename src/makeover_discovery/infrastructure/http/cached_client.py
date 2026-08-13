"""Rate-limited, cached HTTP access to third-party providers.

Every outbound provider call in this service goes through here. Centralising it
means the usage-policy obligations - identify yourself, stay under one request
per second, do not re-fetch what you already have - are satisfied once rather
than remembered separately in each adapter.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any, Final

import httpx

from makeover_discovery.application.ports.cache import ResponseCache
from makeover_discovery.application.ports.rate_limiter import RateLimiter
from makeover_discovery.domain.errors import UpstreamError

MAX_LOGGED_BODY_CHARS: Final = 200
"""Upstream error bodies are truncated before they reach an exception message;
provider payloads can be megabytes and are not diagnostics."""


def _cache_key(method: str, url: str, payload: str) -> str:
    digest = hashlib.sha256(f"{method}\n{url}\n{payload}".encode()).hexdigest()
    return f"http:{digest}"


def _canonical(params: Mapping[str, str]) -> str:
    # Sorted so that two logically identical requests share a cache entry
    # regardless of how the calling adapter happened to order its parameters.
    return "&".join(f"{key}={params[key]}" for key in sorted(params))


class CachedHttpClient:
    """Wraps an ``httpx.AsyncClient`` with caching, throttling, and error mapping."""

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

    async def get_json(self, url: str, params: Mapping[str, str], *, rate_key: str) -> Any:
        return await self._fetch_json("GET", url, _canonical(params), rate_key, params=params)

    async def post_form_json(
        self,
        url: str,
        form: Mapping[str, str],
        *,
        rate_key: str,
    ) -> Any:
        return await self._fetch_json("POST", url, _canonical(form), rate_key, form=form)

    async def _fetch_json(
        self,
        method: str,
        url: str,
        payload: str,
        rate_key: str,
        *,
        params: Mapping[str, str] | None = None,
        form: Mapping[str, str] | None = None,
    ) -> Any:
        key = _cache_key(method, url, payload)
        cached = await self._cache.get(key)
        if cached is not None:
            return _decode(cached, url)

        # Only throttle on a genuine miss. Counting cache hits against the
        # budget would make warm requests needlessly slow for no policy gain.
        await self._rate_limiter.acquire(rate_key)
        text = await self._request_text(method, url, params=params, form=form)
        await self._cache.set(key, text, self._cache_ttl_s)
        return _decode(text, url)

    async def _request_text(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, str] | None,
        form: Mapping[str, str] | None,
    ) -> str:
        headers = {"User-Agent": self._user_agent, "Accept": "application/json"}
        try:
            response = await self._client.request(
                method,
                url,
                params=dict(params) if params is not None else None,
                data=dict(form) if form is not None else None,
                headers=headers,
            )
        except httpx.HTTPError as exc:
            raise UpstreamError(f"{url} could not be reached: {exc}") from exc

        if response.status_code >= httpx.codes.BAD_REQUEST:
            detail = response.text[:MAX_LOGGED_BODY_CHARS]
            raise UpstreamError(f"{url} returned {response.status_code}: {detail}")
        return response.text


def _decode(text: str, url: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise UpstreamError(f"{url} returned a body that is not JSON") from exc

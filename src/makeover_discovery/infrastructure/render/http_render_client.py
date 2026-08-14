"""Submits ``SceneSpec``s to Repo B and polls the resulting job.

Deliberately does not go through ``CachedHttpClient``: that client caches by
``(method, url, payload)``, which is wrong twice over here - a ``POST /jobs``
submission is not idempotent, and a ``GET /jobs/{id}`` poll exists specifically
to observe status *changing* over time, so a cached response would freeze it
and the poll loop would never see ``succeeded``. This talks to the shared
``httpx.AsyncClient`` directly, with its own minimal error mapping mirroring
``CachedHttpClient``'s. There is also no usage-policy rate limit to respect
here, unlike Nominatim/Overpass/Places - Repo B is this system's own service.
"""

from __future__ import annotations

from typing import Any, Final

import httpx
from makeover_contracts.jobs import RenderJob
from makeover_contracts.scene import SceneSpec
from pydantic import ValidationError

from makeover_discovery.domain.errors import NotFoundError, UpstreamError
from makeover_discovery.infrastructure.http.cached_client import MAX_LOGGED_BODY_CHARS

JOBS_PATH: Final = "/jobs"


class HttpRenderClient:
    """The ``RenderClient`` port, implemented over Repo B's job API."""

    def __init__(self, http: httpx.AsyncClient, *, base_url: str, user_agent: str) -> None:
        self._http = http
        self._base_url = base_url.rstrip("/")
        self._user_agent = user_agent

    async def submit(self, spec: SceneSpec) -> RenderJob:
        url = f"{self._base_url}{JOBS_PATH}"
        payload = await self._request("POST", url, json=spec.model_dump(mode="json"))
        return _to_render_job(payload, url)

    async def poll(self, job_id: str) -> RenderJob:
        url = f"{self._base_url}{JOBS_PATH}/{job_id}"
        payload = await self._request("GET", url)
        return _to_render_job(payload, url)

    async def _request(self, method: str, url: str, *, json: Any = None) -> Any:
        headers = {"User-Agent": self._user_agent, "Accept": "application/json"}
        try:
            response = await self._http.request(method, url, json=json, headers=headers)
        except httpx.HTTPError as exc:
            raise UpstreamError(f"{url} could not be reached: {exc}") from exc

        if response.status_code == httpx.codes.NOT_FOUND:
            raise NotFoundError(f"no render job at {url}")
        if response.status_code >= httpx.codes.BAD_REQUEST:
            detail = response.text[:MAX_LOGGED_BODY_CHARS]
            raise UpstreamError(f"{url} returned {response.status_code}: {detail}")

        try:
            return response.json()
        except ValueError as exc:
            raise UpstreamError(f"{url} returned a body that is not JSON") from exc


def _to_render_job(payload: Any, url: str) -> RenderJob:
    try:
        return RenderJob.model_validate(payload)
    except ValidationError as exc:
        # An unparseable job record is worse than none: silently treating it as
        # still-running would spin the poll loop forever on a response that
        # will never change shape.
        raise UpstreamError(f"{url} returned an unusable render job: {exc}") from exc

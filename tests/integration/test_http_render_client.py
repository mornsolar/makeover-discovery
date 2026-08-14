"""``HttpRenderClient``, against a mocked Repo B job API."""

from __future__ import annotations

import httpx
import pytest
import respx

from makeover_discovery.domain.errors import NotFoundError, UpstreamError
from makeover_discovery.infrastructure.render.http_render_client import (
    JOBS_PATH,
    HttpRenderClient,
)
from tests.fakes.render_client import make_render_job
from tests.fakes.specs import make_scene_spec

BASE_URL = "https://render.test"
JOBS_URL = f"{BASE_URL}{JOBS_PATH}"
USER_AGENT = "makeover-discovery-tests/0.1 (+mailto:tests@example.invalid)"


def build(http_client: httpx.AsyncClient) -> HttpRenderClient:
    return HttpRenderClient(http_client, base_url=BASE_URL, user_agent=USER_AGENT)


async def test_submits_the_spec_and_returns_the_created_job(http_client: httpx.AsyncClient):
    spec = make_scene_spec()
    created = make_render_job(spec, job_id="job-1")
    with respx.mock:
        route = respx.post(JOBS_URL).mock(httpx.Response(201, json=created.model_dump(mode="json")))

        job = await build(http_client).submit(spec)

    assert job.id == "job-1"
    assert route.calls.last.request.headers["User-Agent"] == USER_AGENT


async def test_polls_and_returns_the_current_job(http_client: httpx.AsyncClient):
    spec = make_scene_spec()
    running = make_render_job(spec, job_id="job-1")
    with respx.mock:
        respx.get(f"{JOBS_URL}/job-1").mock(
            httpx.Response(200, json=running.model_dump(mode="json"))
        )

        job = await build(http_client).poll("job-1")

    assert job.id == "job-1"


async def test_raises_not_found_for_a_missing_job(http_client: httpx.AsyncClient):
    with respx.mock:
        respx.get(f"{JOBS_URL}/does-not-exist").mock(httpx.Response(404))

        with pytest.raises(NotFoundError):
            await build(http_client).poll("does-not-exist")


async def test_reports_a_spec_the_renderer_rejects(http_client: httpx.AsyncClient):
    spec = make_scene_spec()
    with respx.mock:
        respx.post(JOBS_URL).mock(
            httpx.Response(400, json={"detail": "template requires materials for: ground"})
        )

        with pytest.raises(UpstreamError, match="400"):
            await build(http_client).submit(spec)


async def test_rejects_a_job_record_it_cannot_parse(http_client: httpx.AsyncClient):
    with respx.mock:
        respx.get(f"{JOBS_URL}/job-1").mock(httpx.Response(200, json={"id": "job-1"}))

        with pytest.raises(UpstreamError, match="unusable render job"):
            await build(http_client).poll("job-1")


async def test_reports_an_unreachable_render_service(http_client: httpx.AsyncClient):
    spec = make_scene_spec()
    with respx.mock:
        respx.post(JOBS_URL).mock(side_effect=httpx.ConnectError("connection refused"))

        with pytest.raises(UpstreamError, match="could not be reached"):
            await build(http_client).submit(spec)


async def test_fetches_an_artifacts_bytes(http_client: httpx.AsyncClient):
    with respx.mock:
        respx.get(f"{BASE_URL}/jobs/job-1/artifacts/gltf").mock(
            httpx.Response(200, content=b"glb-bytes")
        )

        data = await build(http_client).fetch_artifact("/jobs/job-1/artifacts/gltf")

    assert data == b"glb-bytes"


async def test_raises_not_found_for_a_missing_artifact(http_client: httpx.AsyncClient):
    with respx.mock:
        respx.get(f"{BASE_URL}/jobs/job-1/artifacts/gltf").mock(httpx.Response(404))

        with pytest.raises(NotFoundError):
            await build(http_client).fetch_artifact("/jobs/job-1/artifacts/gltf")

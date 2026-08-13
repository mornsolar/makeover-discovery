"""Reading the renderer's vocabulary, live and compiled-in."""

from __future__ import annotations

import httpx
import pytest
import respx

from makeover_discovery.domain.errors import UpstreamError
from makeover_discovery.infrastructure.capabilities.http_capability_source import (
    CAPABILITIES_PATH,
    HttpCapabilitySource,
)
from makeover_discovery.infrastructure.capabilities.static_manifest import (
    BUILTIN_MANIFEST,
    StaticCapabilitySource,
)
from makeover_discovery.infrastructure.http.cached_client import CachedHttpClient

BASE_URL = "https://render.test"
URL = f"{BASE_URL}{CAPABILITIES_PATH}"

LIVE_MANIFEST = BUILTIN_MANIFEST.model_copy(
    update={"engine_version": "5.2.0", "material_families": ("timber", "rattan")}
)


def build(cached_http: CachedHttpClient) -> HttpCapabilitySource:
    return HttpCapabilitySource(cached_http, base_url=BASE_URL)


async def test_reads_the_live_manifest(cached_http: CachedHttpClient):
    with respx.mock:
        respx.get(URL).mock(
            httpx.Response(200, json=LIVE_MANIFEST.model_dump(mode="json")),
        )

        manifest = await build(cached_http).manifest()

    assert manifest.engine_version == "5.2.0"
    assert manifest.material_families == ("timber", "rattan")


async def test_rejects_a_manifest_it_cannot_parse(cached_http: CachedHttpClient):
    # Silently accepting a partial manifest would narrow or widen what the model
    # may ask for, without anyone noticing until a render failed.
    with respx.mock:
        respx.get(URL).mock(httpx.Response(200, json={"renderer_name": "makeover-render"}))

        with pytest.raises(UpstreamError, match="unusable manifest"):
            await build(cached_http).manifest()


async def test_reports_an_unreachable_render_service(cached_http: CachedHttpClient):
    with respx.mock:
        respx.get(URL).mock(httpx.Response(503))

        with pytest.raises(UpstreamError):
            await build(cached_http).manifest()


async def test_the_builtin_manifest_serves_without_a_render_service():
    manifest = await StaticCapabilitySource().manifest()

    assert manifest.material_families == BUILTIN_MANIFEST.material_families


async def test_the_builtin_manifest_is_honest_about_the_engine():
    # It has not spoken to a renderer, so it must not claim a Blender build.
    assert (await StaticCapabilitySource().manifest()).engine_version == "unknown"

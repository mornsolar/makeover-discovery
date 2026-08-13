"""Rate-limited, cached provider access.

No test here touches the network: respx intercepts at the transport layer, so
what is exercised is the real httpx request path with a stubbed socket.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from makeover_discovery.domain.errors import UpstreamError
from tests.integration.conftest import TEST_USER_AGENT

BASE_URL = "https://provider.test"
ENDPOINT = f"{BASE_URL}/search"
RATE_KEY = "provider"


async def test_returns_the_decoded_payload(cached_http):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/search").mock(return_value=httpx.Response(200, json={"ok": True}))

        payload = await cached_http.get_json(ENDPOINT, {"q": "50450"}, rate_key=RATE_KEY)

    assert payload == {"ok": True}


async def test_identifies_itself_to_the_provider(cached_http):
    # Nominatim's usage policy blocks clients that do not; this assertion is
    # the only thing standing between us and a silent IP ban.
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/search").mock(return_value=httpx.Response(200, json=[]))

        await cached_http.get_json(ENDPOINT, {"q": "50450"}, rate_key=RATE_KEY)

    assert route.calls.last.request.headers["User-Agent"] == TEST_USER_AGENT


async def test_serves_a_repeated_request_from_cache(cached_http):
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/search").mock(return_value=httpx.Response(200, json={"ok": True}))

        await cached_http.get_json(ENDPOINT, {"q": "50450"}, rate_key=RATE_KEY)
        await cached_http.get_json(ENDPOINT, {"q": "50450"}, rate_key=RATE_KEY)

    assert route.call_count == 1


async def test_ignores_parameter_ordering_when_matching_the_cache(cached_http):
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/search").mock(return_value=httpx.Response(200, json={"ok": True}))

        await cached_http.get_json(ENDPOINT, {"a": "1", "b": "2"}, rate_key=RATE_KEY)
        await cached_http.get_json(ENDPOINT, {"b": "2", "a": "1"}, rate_key=RATE_KEY)

    assert route.call_count == 1


async def test_fetches_again_for_different_parameters(cached_http):
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/search").mock(return_value=httpx.Response(200, json={"ok": True}))

        await cached_http.get_json(ENDPOINT, {"q": "50450"}, rate_key=RATE_KEY)
        await cached_http.get_json(ENDPOINT, {"q": "50460"}, rate_key=RATE_KEY)

    assert route.call_count == 2


async def test_throttles_only_the_calls_that_reach_the_network(cached_http, rate_limiter):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/search").mock(return_value=httpx.Response(200, json={"ok": True}))

        await cached_http.get_json(ENDPOINT, {"q": "50450"}, rate_key=RATE_KEY)
        await cached_http.get_json(ENDPOINT, {"q": "50450"}, rate_key=RATE_KEY)

    assert rate_limiter.keys == [RATE_KEY]


async def test_posts_a_form_body(cached_http):
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post("/interpreter").mock(return_value=httpx.Response(200, json={"ok": True}))

        await cached_http.post_form_json(
            f"{BASE_URL}/interpreter", {"data": "[out:json];"}, rate_key=RATE_KEY
        )

    assert b"data=" in route.calls.last.request.content


async def test_reports_an_error_status_as_an_upstream_failure(cached_http):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/search").mock(return_value=httpx.Response(429, text="slow down"))

        with pytest.raises(UpstreamError, match="429"):
            await cached_http.get_json(ENDPOINT, {"q": "50450"}, rate_key=RATE_KEY)


async def test_reports_an_unreachable_host_as_an_upstream_failure(cached_http):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/search").mock(side_effect=httpx.ConnectError("no route"))

        with pytest.raises(UpstreamError, match="could not be reached"):
            await cached_http.get_json(ENDPOINT, {"q": "50450"}, rate_key=RATE_KEY)


async def test_reports_a_non_json_body_as_an_upstream_failure(cached_http):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/search").mock(return_value=httpx.Response(200, text="<html>maintenance</html>"))

        with pytest.raises(UpstreamError, match="not JSON"):
            await cached_http.get_json(ENDPOINT, {"q": "50450"}, rate_key=RATE_KEY)


async def test_does_not_cache_a_failed_response(cached_http):
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/search").mock(
            side_effect=[
                httpx.Response(503, text="unavailable"),
                httpx.Response(200, json={"ok": True}),
            ]
        )

        with pytest.raises(UpstreamError):
            await cached_http.get_json(ENDPOINT, {"q": "50450"}, rate_key=RATE_KEY)
        payload = await cached_http.get_json(ENDPOINT, {"q": "50450"}, rate_key=RATE_KEY)

    assert payload == {"ok": True}
    assert route.call_count == 2

"""Plain HTTP page fetching."""

from __future__ import annotations

import httpx
import pytest
import respx

from makeover_discovery.domain.errors import PolicyViolationError
from makeover_discovery.domain.model.web import MAX_HTML_BYTES
from makeover_discovery.infrastructure.crawl.httpx_fetcher import HttpxWebFetcher
from tests.fakes.clock import FixedClock
from tests.fakes.web import AllowAllRobots, DenyAllRobots
from tests.integration.conftest import TEST_USER_AGENT

BASE_URL = "https://ali.example"
PAGE_URL = f"{BASE_URL}/menu"
HTML = "<html><body>Kedai Kopi Ali</body></html>"
HTML_HEADERS = {"content-type": "text/html; charset=utf-8"}


def build(http_client, rate_limiter, robots=None) -> HttpxWebFetcher:
    return HttpxWebFetcher(
        http_client,
        robots or AllowAllRobots(),
        FixedClock(),
        rate_limiter=rate_limiter,
        user_agent=TEST_USER_AGENT,
    )


@pytest.fixture
def fetcher(http_client, rate_limiter) -> HttpxWebFetcher:
    return build(http_client, rate_limiter)


async def test_returns_the_fetched_page(fetcher):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/menu").mock(return_value=httpx.Response(200, text=HTML, headers=HTML_HEADERS))

        page = await fetcher.fetch(PAGE_URL)

    assert page is not None
    assert page.html == HTML
    assert page.fetched_at == FixedClock().now()


async def test_identifies_itself_to_the_host(fetcher):
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/menu").mock(
            return_value=httpx.Response(200, text=HTML, headers=HTML_HEADERS)
        )

        await fetcher.fetch(PAGE_URL)

    assert route.calls.last.request.headers["User-Agent"] == TEST_USER_AGENT


async def test_refuses_a_page_robots_disallows(http_client, rate_limiter):
    # The gate is inside the fetcher rather than beside it: a check the caller
    # has to remember is a check that eventually goes unmade.
    fetcher = build(http_client, rate_limiter, DenyAllRobots())

    with pytest.raises(PolicyViolationError, match=r"robots\.txt"):
        await fetcher.fetch(PAGE_URL)


async def test_does_not_request_a_page_robots_disallows(http_client, rate_limiter):
    fetcher = build(http_client, rate_limiter, DenyAllRobots())
    with respx.mock(base_url=BASE_URL, assert_all_called=False) as mock:
        route = mock.get("/menu").mock(return_value=httpx.Response(200, text=HTML))

        with pytest.raises(PolicyViolationError):
            await fetcher.fetch(PAGE_URL)

    assert route.call_count == 0


async def test_throttles_per_host(fetcher, rate_limiter):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/menu").mock(return_value=httpx.Response(200, text=HTML, headers=HTML_HEADERS))

        await fetcher.fetch(PAGE_URL)

    assert rate_limiter.keys == ["ali.example"]


async def test_returns_nothing_for_a_dead_site(fetcher):
    # A business whose website has lapsed is an ordinary finding, not a failure
    # worth aborting an enrichment run for.
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/menu").mock(side_effect=httpx.ConnectError("no route"))

        assert await fetcher.fetch(PAGE_URL) is None


async def test_returns_nothing_for_an_error_status(fetcher):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/menu").mock(return_value=httpx.Response(404, text="gone"))

        assert await fetcher.fetch(PAGE_URL) is None


async def test_returns_nothing_for_a_non_html_document(fetcher):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/menu").mock(
            return_value=httpx.Response(
                200, content=b"%PDF-1.7", headers={"content-type": "application/pdf"}
            )
        )

        assert await fetcher.fetch(PAGE_URL) is None


async def test_returns_nothing_for_an_oversized_document(fetcher):
    oversized = "<html>" + "x" * (MAX_HTML_BYTES + 1) + "</html>"
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/menu").mock(
            return_value=httpx.Response(200, text=oversized, headers=HTML_HEADERS)
        )

        assert await fetcher.fetch(PAGE_URL) is None


async def test_records_the_url_it_landed_on_after_redirects(fetcher):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/menu").mock(
            return_value=httpx.Response(301, headers={"location": f"{BASE_URL}/food"})
        )
        mock.get("/food").mock(return_value=httpx.Response(200, text=HTML, headers=HTML_HEADERS))

        page = await fetcher.fetch(PAGE_URL)

    assert page is not None
    assert page.was_redirected
    assert page.final_url == f"{BASE_URL}/food"


async def test_refuses_a_url_that_is_not_http(http_client, rate_limiter):
    fetcher = build(http_client, rate_limiter)

    with pytest.raises(PolicyViolationError):
        await fetcher.fetch("ftp://ali.example/menu")

"""Escalating from a plain fetch to a rendered one."""

from __future__ import annotations

from makeover_discovery.infrastructure.crawl.fallback_fetcher import FallbackWebFetcher
from tests.fakes.web import FakeWebFetcher, make_page

THIN_PAGE = make_page("<html><body><div id='root'></div></body></html>")
RICH_PAGE = make_page("<html><body>" + "Kedai Kopi Ali serves coffee. " * 10 + "</body></html>")
RENDERED_PAGE = make_page("<html><body>Rendered menu content.</body></html>")


def build(primary: FakeWebFetcher, fallback: FakeWebFetcher) -> FallbackWebFetcher:
    return FallbackWebFetcher(primary, fallback)


async def test_returns_the_primary_result_when_it_already_has_content():
    primary = FakeWebFetcher(RICH_PAGE)
    fallback = FakeWebFetcher(RENDERED_PAGE)

    page = await build(primary, fallback).fetch("https://ali.example")

    assert page is RICH_PAGE


async def test_does_not_invoke_the_fallback_when_the_primary_already_succeeded():
    # A browser boot costs roughly two orders of magnitude more than an HTTP
    # request; it must only ever run when actually needed.
    primary = FakeWebFetcher(RICH_PAGE)
    fallback = FakeWebFetcher(RENDERED_PAGE)

    await build(primary, fallback).fetch("https://ali.example")

    assert fallback.urls == []


async def test_escalates_when_the_primary_result_looks_like_a_js_shell():
    primary = FakeWebFetcher(THIN_PAGE)
    fallback = FakeWebFetcher(RENDERED_PAGE)

    page = await build(primary, fallback).fetch("https://ali.example")

    assert page is RENDERED_PAGE


async def test_returns_nothing_without_escalating_when_the_primary_found_no_page():
    # A dead link is not something a browser will load differently.
    primary = FakeWebFetcher(None)
    fallback = FakeWebFetcher(RENDERED_PAGE)

    page = await build(primary, fallback).fetch("https://ali.example")

    assert page is None
    assert fallback.urls == []


async def test_keeps_the_thin_shell_when_the_fallback_also_finds_nothing():
    # A thin server-rendered page still beats an enrichment run with nothing.
    primary = FakeWebFetcher(THIN_PAGE)
    fallback = FakeWebFetcher(None)

    page = await build(primary, fallback).fetch("https://ali.example")

    assert page is THIN_PAGE


async def test_fetches_the_same_url_from_both_fetchers():
    primary = FakeWebFetcher(THIN_PAGE)
    fallback = FakeWebFetcher(RENDERED_PAGE)

    await build(primary, fallback).fetch("https://ali.example/menu")

    assert primary.urls == ["https://ali.example/menu"]
    assert fallback.urls == ["https://ali.example/menu"]


async def test_honours_a_custom_escalation_predicate():
    always_escalate = FallbackWebFetcher(
        FakeWebFetcher(RICH_PAGE),
        FakeWebFetcher(RENDERED_PAGE),
        should_escalate=lambda page: True,
    )

    page = await always_escalate.fetch("https://ali.example")

    assert page is RENDERED_PAGE

"""Overpass parsing against recorded response shapes."""

from __future__ import annotations

import httpx
import pytest
import respx
from makeover_contracts.business import BusinessCategory
from makeover_contracts.geo import CircleArea, GeoPoint
from makeover_contracts.provenance import DataLicense, DataSource

from makeover_discovery.domain.errors import UpstreamError
from makeover_discovery.domain.model.discovery import SearchFilters
from makeover_discovery.infrastructure.directory.overpass import OverpassDirectory
from tests.fakes.clock import FixedClock

BASE_URL = "https://overpass.test"
AREA = CircleArea(center=GeoPoint(lat=3.16, lon=101.71), radius_m=1500.0)

CAFE_NODE = {
    "type": "node",
    "id": 1,
    "lat": 3.1601,
    "lon": 101.7101,
    "tags": {
        "name": "Kedai Kopi Ali",
        "amenity": "cafe",
        "addr:housenumber": "12",
        "addr:street": "Jalan Ampang",
        "addr:city": "Kuala Lumpur",
        "website": "https://kedaikopiali.example",
    },
}
BAKERY_WAY = {
    "type": "way",
    "id": 2,
    "center": {"lat": 3.1605, "lon": 101.7105},
    "tags": {"name": "Roti Bakar", "shop": "bakery"},
}


def build(cached_http) -> OverpassDirectory:
    return OverpassDirectory(cached_http, FixedClock(), base_url=BASE_URL)


async def search(cached_http, elements, filters: SearchFilters | None = None):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.post("/interpreter").mock(
            return_value=httpx.Response(200, json={"elements": elements})
        )
        return await build(cached_http).search(AREA, filters or SearchFilters())


async def test_reads_a_node_into_a_candidate(cached_http):
    candidates = await search(cached_http, [CAFE_NODE])

    assert len(candidates) == 1
    assert candidates[0].name == "Kedai Kopi Ali"
    assert candidates[0].category is BusinessCategory.CAFE
    assert candidates[0].external_id == "node/1"


async def test_places_a_way_at_its_computed_centre(cached_http):
    candidates = await search(cached_http, [BAKERY_WAY])

    assert candidates[0].location == GeoPoint(lat=3.1605, lon=101.7105)


async def test_assembles_a_readable_address(cached_http):
    candidates = await search(cached_http, [CAFE_NODE])

    assert candidates[0].address_line == "12 Jalan Ampang, Kuala Lumpur"


async def test_records_the_odbl_licence_on_every_candidate(cached_http):
    # Attribution on the landing page is derived from this, so an adapter that
    # forgot it would silently produce a licence breach downstream.
    source = (await search(cached_http, [CAFE_NODE]))[0].source

    assert source.source is DataSource.OPENSTREETMAP
    assert source.license is DataLicense.ODBL_1_0
    assert source.attribution == "© OpenStreetMap contributors"


async def test_stamps_candidates_with_the_injected_clock(cached_http):
    source = (await search(cached_http, [CAFE_NODE]))[0].source

    assert source.fetched_at == FixedClock().now()


async def test_links_back_to_the_openstreetmap_object(cached_http):
    source = (await search(cached_http, [CAFE_NODE]))[0].source

    assert source.url == "https://www.openstreetmap.org/node/1"


async def test_skips_features_without_a_name(cached_http):
    unnamed = {"type": "node", "id": 3, "lat": 3.16, "lon": 101.71, "tags": {"amenity": "cafe"}}

    assert await search(cached_http, [unnamed]) == ()


async def test_skips_features_that_are_not_businesses(cached_http):
    bus_stop = {
        "type": "node",
        "id": 4,
        "lat": 3.16,
        "lon": 101.71,
        "tags": {"name": "Stesen Bas", "highway": "bus_stop"},
    }

    assert await search(cached_http, [bus_stop]) == ()


async def test_skips_a_way_with_no_centre(cached_http):
    centreless = {"type": "way", "id": 5, "tags": {"name": "Kedai", "shop": "bakery"}}

    assert await search(cached_http, [centreless]) == ()


async def test_skips_entries_that_are_not_objects(cached_http):
    assert await search(cached_http, ["unexpected", 7]) == ()


async def test_discards_a_website_value_that_is_not_a_link(cached_http):
    # OpenStreetMap holds bare domains and even phone numbers in this tag.
    bare = {
        "type": "node",
        "id": 6,
        "lat": 3.16,
        "lon": 101.71,
        "tags": {"name": "Kedai", "shop": "bakery", "website": "kedai.example"},
    }

    assert (await search(cached_http, [bare]))[0].website is None


async def test_falls_back_to_the_contact_website_tag(cached_http):
    contact = {
        "type": "node",
        "id": 7,
        "lat": 3.16,
        "lon": 101.71,
        "tags": {
            "name": "Kedai",
            "shop": "bakery",
            "contact:website": "https://kedai.example",
        },
    }

    assert (await search(cached_http, [contact]))[0].website == "https://kedai.example"


async def test_sends_the_generated_query_as_the_request_body(cached_http):
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post("/interpreter").mock(
            return_value=httpx.Response(200, json={"elements": []})
        )

        await build(cached_http).search(AREA, SearchFilters(categories=(BusinessCategory.CAFE,)))

    assert "amenity" in route.calls.last.request.content.decode()


async def test_rejects_a_payload_that_is_not_an_object(cached_http):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.post("/interpreter").mock(return_value=httpx.Response(200, json=[1, 2]))

        with pytest.raises(UpstreamError, match="not an object"):
            await build(cached_http).search(AREA, SearchFilters())


async def test_rejects_a_payload_without_elements(cached_http):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.post("/interpreter").mock(return_value=httpx.Response(200, json={"version": 0.6}))

        with pytest.raises(UpstreamError, match="elements"):
            await build(cached_http).search(AREA, SearchFilters())

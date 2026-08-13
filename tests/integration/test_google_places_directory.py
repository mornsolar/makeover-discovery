"""Google Places parsing against recorded response shapes."""

from __future__ import annotations

import httpx
import pytest
import respx
from makeover_contracts.business import BusinessCategory
from makeover_contracts.geo import CircleArea, GeoPoint, PolygonArea
from makeover_contracts.provenance import DataLicense, DataSource

from makeover_discovery.domain.errors import UpstreamError
from makeover_discovery.domain.model.discovery import MAX_RESULT_LIMIT, SearchFilters
from makeover_discovery.domain.policy.retention import RetentionPolicy
from makeover_discovery.infrastructure.directory.google_places import (
    MAX_RESULT_COUNT,
    GooglePlacesDirectory,
    build_request,
)
from tests.fakes.clock import FixedClock

BASE_URL = "https://places.test"
API_KEY = "test-key"
CIRCLE = CircleArea(center=GeoPoint(lat=3.16, lon=101.71), radius_m=1500.0)
TRIANGLE = PolygonArea(
    vertices=(
        GeoPoint(lat=3.15, lon=101.70),
        GeoPoint(lat=3.17, lon=101.70),
        GeoPoint(lat=3.16, lon=101.72),
    )
)

CAFE_PLACE = {
    "id": "places/cafe1",
    "displayName": {"text": "Kedai Kopi Ali"},
    "primaryType": "cafe",
    "types": ["cafe", "food"],
    "location": {"latitude": 3.1601, "longitude": 101.7101},
    "formattedAddress": "12 Jalan Ampang, Kuala Lumpur",
    "websiteUri": "https://kedaikopiali.example",
}


def build(cached_http) -> GooglePlacesDirectory:
    return GooglePlacesDirectory(
        cached_http,
        FixedClock(),
        base_url=BASE_URL,
        api_key=API_KEY,
        retention=RetentionPolicy(),
    )


async def search(cached_http, places, filters: SearchFilters | None = None):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.post("/places:searchNearby").mock(
            return_value=httpx.Response(200, json={"places": places})
        )
        return await build(cached_http).search(CIRCLE, filters or SearchFilters())


async def test_reads_a_place_into_a_candidate(cached_http):
    candidates = await search(cached_http, [CAFE_PLACE])

    assert len(candidates) == 1
    assert candidates[0].name == "Kedai Kopi Ali"
    assert candidates[0].category is BusinessCategory.CAFE
    assert candidates[0].external_id == "places/cafe1"


async def test_reads_the_address_and_website(cached_http):
    candidate = (await search(cached_http, [CAFE_PLACE]))[0]

    assert candidate.address_line == "12 Jalan Ampang, Kuala Lumpur"
    assert candidate.website == "https://kedaikopiali.example"


async def test_records_the_places_licence_and_a_thirty_day_retention_window(cached_http):
    # This is the payoff of building RetentionPolicy generically in Phase 2:
    # Places gets its 30-day cap for free, exactly the same way OSM gets none.
    source = (await search(cached_http, [CAFE_PLACE]))[0].source

    assert source.source is DataSource.GOOGLE_PLACES
    assert source.license is DataLicense.GOOGLE_PLACES_TOS
    assert source.attribution == "Powered by Google"
    assert source.retention_until is not None
    assert (source.retention_until - source.fetched_at).days == 30


async def test_authenticates_with_the_api_key_header(cached_http):
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post("/places:searchNearby").mock(
            return_value=httpx.Response(200, json={"places": []})
        )

        await build(cached_http).search(CIRCLE, SearchFilters())

    assert route.calls.last.request.headers["X-Goog-Api-Key"] == API_KEY


async def test_requests_only_the_fields_the_candidate_model_uses(cached_http):
    # Places bills per requested field; a wide field mask costs real money for
    # data this adapter would just discard.
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post("/places:searchNearby").mock(
            return_value=httpx.Response(200, json={"places": []})
        )

        await build(cached_http).search(CIRCLE, SearchFilters())

    mask = route.calls.last.request.headers["X-Goog-FieldMask"]
    assert "places.displayName" in mask
    assert "places.location" in mask


async def test_skips_a_place_with_no_recognised_type(cached_http):
    unclassified = {**CAFE_PLACE, "types": ["point_of_interest"]}

    assert await search(cached_http, [unclassified]) == ()


async def test_skips_a_place_without_a_location(cached_http):
    locationless = {k: v for k, v in CAFE_PLACE.items() if k != "location"}

    assert await search(cached_http, [locationless]) == ()


async def test_skips_a_place_without_a_display_name(cached_http):
    nameless = {k: v for k, v in CAFE_PLACE.items() if k != "displayName"}

    assert await search(cached_http, [nameless]) == ()


async def test_rejects_a_payload_that_is_not_an_object(cached_http):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.post("/places:searchNearby").mock(return_value=httpx.Response(200, json=[1, 2]))

        with pytest.raises(UpstreamError, match="not an object"):
            await build(cached_http).search(CIRCLE, SearchFilters())


async def test_rejects_a_payload_whose_places_field_is_not_a_list(cached_http):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.post("/places:searchNearby").mock(
            return_value=httpx.Response(200, json={"places": "oops"})
        )

        with pytest.raises(UpstreamError, match="places"):
            await build(cached_http).search(CIRCLE, SearchFilters())


def test_builds_a_circle_request_from_a_circle_area():
    body = build_request(CIRCLE, SearchFilters())

    assert body["locationRestriction"]["circle"]["radius"] == 1500.0
    assert body["locationRestriction"]["circle"]["center"] == {
        "latitude": 3.16,
        "longitude": 101.71,
    }


def test_builds_a_circle_request_from_a_polygon_area():
    # Places only accepts a centre and radius; a polygon boundary is reduced to
    # the circle that covers every vertex.
    body = build_request(TRIANGLE, SearchFilters())

    assert body["locationRestriction"]["circle"]["radius"] > 0


def test_clamps_the_result_count_to_places_own_ceiling():
    body = build_request(CIRCLE, SearchFilters(limit=MAX_RESULT_LIMIT))

    assert body["maxResultCount"] == MAX_RESULT_COUNT


def test_requests_no_more_than_the_caller_asked_for():
    body = build_request(CIRCLE, SearchFilters(limit=5))

    assert body["maxResultCount"] == 5


def test_requests_every_type_when_no_category_is_given():
    body = build_request(CIRCLE, SearchFilters())

    assert "cafe" in body["includedTypes"]


def test_narrows_included_types_to_the_requested_category():
    body = build_request(CIRCLE, SearchFilters(categories=(BusinessCategory.BAKERY,)))

    assert body["includedTypes"] == ["bakery"]

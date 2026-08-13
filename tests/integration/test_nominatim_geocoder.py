"""Nominatim geocoding against recorded response shapes."""

from __future__ import annotations

import httpx
import respx
from makeover_contracts.geo import CircleArea, PolygonArea, Postcode

from makeover_discovery.infrastructure.geocoding.nominatim import (
    MAX_AREA_VERTICES,
    NominatimGeocoder,
)

BASE_URL = "https://nominatim.test"
POSTCODE = Postcode(value="50450", country="MY")
DEFAULT_RADIUS_M = 1500.0
MAX_RADIUS_M = 2500.0

POINT_RESULT = {
    "lat": "3.1600",
    "lon": "101.7100",
    "boundingbox": ["3.1500", "3.1700", "101.7000", "101.7200"],
}
POLYGON_RESULT = {
    "lat": "3.1600",
    "lon": "101.7100",
    # GeoJSON is longitude-first; the adapter must not read these as lat/lon.
    "geojson": {
        "type": "Polygon",
        "coordinates": [
            [[101.70, 3.15], [101.72, 3.15], [101.72, 3.17], [101.70, 3.17], [101.70, 3.15]]
        ],
    },
}


def build(cached_http) -> NominatimGeocoder:
    return NominatimGeocoder(
        cached_http,
        base_url=BASE_URL,
        default_radius_m=DEFAULT_RADIUS_M,
        max_radius_m=MAX_RADIUS_M,
    )


async def test_prefers_a_boundary_polygon_when_one_exists(cached_http):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/search").mock(return_value=httpx.Response(200, json=[POLYGON_RESULT]))

        area = await build(cached_http).geocode(POSTCODE)

    assert isinstance(area, PolygonArea)
    assert len(area.vertices) == 4


async def test_reads_geojson_coordinates_longitude_first(cached_http):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/search").mock(return_value=httpx.Response(200, json=[POLYGON_RESULT]))

        area = await build(cached_http).geocode(POSTCODE)

    assert isinstance(area, PolygonArea)
    # Latitudes stay near 3 and longitudes near 101; swapping them would put
    # this search area in the Indian Ocean.
    assert all(3.0 < vertex.lat < 4.0 for vertex in area.vertices)
    assert all(101.0 < vertex.lon < 102.0 for vertex in area.vertices)


async def test_drops_the_repeated_closing_vertex(cached_http):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/search").mock(return_value=httpx.Response(200, json=[POLYGON_RESULT]))

        area = await build(cached_http).geocode(POSTCODE)

    assert isinstance(area, PolygonArea)
    assert area.vertices[0] != area.vertices[-1]


async def test_thins_a_boundary_that_overpass_could_not_accept(cached_http):
    ring = [[101.70 + index / 10_000, 3.15 + index / 10_000] for index in range(500)]
    detailed = {"geojson": {"type": "Polygon", "coordinates": [ring]}}
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/search").mock(return_value=httpx.Response(200, json=[detailed]))

        area = await build(cached_http).geocode(POSTCODE)

    assert isinstance(area, PolygonArea)
    assert len(area.vertices) <= MAX_AREA_VERTICES


async def test_uses_the_first_part_of_a_multipolygon(cached_http):
    multi = {
        "geojson": {
            "type": "MultiPolygon",
            "coordinates": [POLYGON_RESULT["geojson"]["coordinates"], []],
        }
    }
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/search").mock(return_value=httpx.Response(200, json=[multi]))

        area = await build(cached_http).geocode(POSTCODE)

    assert isinstance(area, PolygonArea)


async def test_falls_back_to_a_circle_sized_from_the_bounding_box(cached_http):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/search").mock(return_value=httpx.Response(200, json=[POINT_RESULT]))

        area = await build(cached_http).geocode(POSTCODE)

    assert isinstance(area, CircleArea)
    assert area.center.lat == 3.16
    assert area.radius_m != DEFAULT_RADIUS_M


async def test_uses_the_configured_radius_when_no_bounding_box_is_given(cached_http):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/search").mock(
            return_value=httpx.Response(200, json=[{"lat": "3.16", "lon": "101.71"}])
        )

        area = await build(cached_http).geocode(POSTCODE)

    assert isinstance(area, CircleArea)
    assert area.radius_m == DEFAULT_RADIUS_M


async def test_retries_as_free_text_when_the_structured_lookup_is_empty(cached_http):
    # Malaysian postcodes frequently have no dedicated postal_code object in
    # OpenStreetMap, so the free-text pass is the common path, not an edge case.
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/search").mock(
            side_effect=[
                httpx.Response(200, json=[]),
                httpx.Response(200, json=[POINT_RESULT]),
            ]
        )

        area = await build(cached_http).geocode(POSTCODE)

    assert route.call_count == 2
    assert isinstance(area, CircleArea)
    assert "postalcode=50450" in str(route.calls[0].request.url)
    assert "q=50450" in str(route.calls[1].request.url)


async def test_scopes_the_search_to_the_requested_country(cached_http):
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/search").mock(return_value=httpx.Response(200, json=[POINT_RESULT]))

        await build(cached_http).geocode(POSTCODE)

    assert "countrycodes=my" in str(route.calls.last.request.url)


async def test_returns_none_when_no_lookup_finds_anything(cached_http):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/search").mock(return_value=httpx.Response(200, json=[]))

        assert await build(cached_http).geocode(POSTCODE) is None


async def test_returns_none_for_a_result_without_usable_coordinates(cached_http):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/search").mock(return_value=httpx.Response(200, json=[{"lat": "north"}]))

        assert await build(cached_http).geocode(POSTCODE) is None


async def test_ignores_a_malformed_polygon_and_uses_the_point(cached_http):
    broken = {"lat": "3.16", "lon": "101.71", "geojson": {"type": "Polygon", "coordinates": []}}
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/search").mock(return_value=httpx.Response(200, json=[broken]))

        area = await build(cached_http).geocode(POSTCODE)

    assert isinstance(area, CircleArea)


async def test_caps_a_radius_inferred_from_a_padded_bounding_box(cached_http):
    # Nominatim reports a ~10 km box around a postcode *point*, which would
    # otherwise pull in whole neighbouring postcodes. Observed live for 50450.
    padded = {
        "lat": "3.1572",
        "lon": "101.7173",
        "boundingbox": ["3.1120285", "3.2023964", "101.6724079", "101.7623092"],
    }
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/search").mock(return_value=httpx.Response(200, json=[padded]))

        area = await build(cached_http).geocode(POSTCODE)

    assert isinstance(area, CircleArea)
    assert area.radius_m == MAX_RADIUS_M

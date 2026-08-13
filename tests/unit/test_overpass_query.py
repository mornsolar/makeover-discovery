"""Overpass query generation.

Asserted directly rather than through the adapter: a malformed query is the
single most likely cause of an empty result set, and it is far cheaper to catch
here than in an HTTP-level test.
"""

from __future__ import annotations

from makeover_contracts.business import BusinessCategory
from makeover_contracts.geo import CircleArea, GeoPoint, PolygonArea

from makeover_discovery.domain.model.discovery import SearchFilters
from makeover_discovery.infrastructure.directory.overpass import build_query

CIRCLE = CircleArea(center=GeoPoint(lat=3.16, lon=101.71), radius_m=1500.0)
TRIANGLE = PolygonArea(
    vertices=(
        GeoPoint(lat=3.15, lon=101.70),
        GeoPoint(lat=3.17, lon=101.70),
        GeoPoint(lat=3.16, lon=101.72),
    )
)


def test_asks_for_json_and_bounds_the_server_side_work():
    query = build_query(CIRCLE, SearchFilters())

    assert query.startswith("[out:json][timeout:")


def test_searches_a_circle_around_the_centre():
    query = build_query(CIRCLE, SearchFilters())

    assert "(around:1500,3.160000,101.710000)" in query


def test_searches_within_a_polygon_boundary():
    query = build_query(TRIANGLE, SearchFilters())

    assert '(poly:"3.150000 101.700000 3.170000 101.700000 3.160000 101.720000")' in query


def test_requests_tags_and_centres_so_ways_can_be_placed():
    query = build_query(CIRCLE, SearchFilters())

    assert "out tags center qt" in query


def test_sets_no_element_limit():
    # Overpass truncates by quadtile, an ordering unrelated to distance from
    # our centre. Against live Kuala Lumpur data a 500-element cap returned
    # nothing closer than 1.2 km when the true nearest was 77 m, so ranking
    # has to happen here over the whole area.
    query = build_query(CIRCLE, SearchFilters(limit=5))

    assert query.rstrip().endswith("out tags center qt;")


def test_generates_one_query_for_any_limit_so_the_cache_is_shared():
    assert build_query(CIRCLE, SearchFilters(limit=5)) == build_query(
        CIRCLE, SearchFilters(limit=40)
    )


def test_emits_one_statement_per_selector():
    query = build_query(CIRCLE, SearchFilters(categories=(BusinessCategory.CAFE,)))

    assert query.count("nwr") == 1
    assert 'nwr["amenity"="cafe"](around:' in query

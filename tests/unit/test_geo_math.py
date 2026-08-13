"""Great-circle helpers."""

from __future__ import annotations

from makeover_contracts.geo import GeoPoint, PolygonArea

from makeover_discovery.domain.model.geo_math import (
    bounding_box_radius_m,
    haversine_m,
    polygon_radius_m,
)

KUALA_LUMPUR = GeoPoint(lat=3.1390, lon=101.6869)
SINGAPORE = GeoPoint(lat=1.3521, lon=103.8198)
KM = 1000.0


def test_returns_zero_for_identical_points():
    assert haversine_m(KUALA_LUMPUR, KUALA_LUMPUR) == 0.0


def test_measures_a_known_intercity_distance():
    # Kuala Lumpur to Singapore is ~309 km great-circle; a 2 km tolerance
    # catches a wrong radius or a degrees/radians slip without being brittle.
    distance = haversine_m(KUALA_LUMPUR, SINGAPORE)

    assert abs(distance - 309 * KM) < 2 * KM


def test_is_symmetric():
    assert haversine_m(KUALA_LUMPUR, SINGAPORE) == haversine_m(SINGAPORE, KUALA_LUMPUR)


def test_swapping_latitude_and_longitude_changes_the_answer():
    # Guards the GeoJSON longitude-first parsing in the geocoder: if this ever
    # became symmetric, a coordinate-order bug would pass unnoticed.
    swapped = GeoPoint(lat=SINGAPORE.lon - 100, lon=SINGAPORE.lat)

    assert haversine_m(KUALA_LUMPUR, swapped) != haversine_m(KUALA_LUMPUR, SINGAPORE)


def test_bounding_box_radius_is_half_the_diagonal():
    south, north, west, east = 3.10, 3.20, 101.60, 101.75

    radius = bounding_box_radius_m(south, north, west, east)
    diagonal = haversine_m(GeoPoint(lat=south, lon=west), GeoPoint(lat=north, lon=east))

    assert radius == diagonal / 2


def test_bounding_box_radius_is_zero_for_a_degenerate_box():
    assert bounding_box_radius_m(3.16, 3.16, 101.71, 101.71) == 0.0


def test_polygon_radius_covers_the_farthest_vertex():
    triangle = PolygonArea(
        vertices=(
            GeoPoint(lat=3.15, lon=101.70),
            GeoPoint(lat=3.17, lon=101.70),
            GeoPoint(lat=3.16, lon=101.72),
        )
    )
    center = triangle.query_center

    radius = polygon_radius_m(triangle)

    assert radius == max(haversine_m(center, vertex) for vertex in triangle.vertices)


def test_polygon_radius_is_zero_for_a_degenerate_polygon():
    point = GeoPoint(lat=3.16, lon=101.71)
    degenerate = PolygonArea(vertices=(point, point, point))

    assert polygon_radius_m(degenerate) == 0.0

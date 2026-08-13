"""Great-circle helpers.

Pure functions over value objects - no I/O, no framework. They live in
``domain`` so adapters, use cases, and tests all share one definition of "how
far apart", rather than each rolling its own approximation.
"""

from __future__ import annotations

import math
from typing import Final

from makeover_contracts.geo import GeoPoint

EARTH_RADIUS_M: Final = 6_371_008.8
"""IUGG mean Earth radius. Ample for sizing a search radius; we are not
navigating, and the ellipsoidal error is well under a metre per kilometre."""


def haversine_m(origin: GeoPoint, destination: GeoPoint) -> float:
    """Great-circle distance in metres between two WGS-84 points."""
    lat1, lon1 = math.radians(origin.lat), math.radians(origin.lon)
    lat2, lon2 = math.radians(destination.lat), math.radians(destination.lon)
    half_lat = (lat2 - lat1) / 2
    half_lon = (lon2 - lon1) / 2
    a = math.sin(half_lat) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(half_lon) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def bounding_box_radius_m(south: float, north: float, west: float, east: float) -> float:
    """Radius of the circle that circumscribes a lat/lon bounding box.

    Half the box diagonal, so the circle covers every corner rather than
    clipping them. Geocoders hand back a box far more often than a polygon, and
    a circle is what the directory adapters can actually query with.
    """
    south_west = GeoPoint(lat=south, lon=west)
    north_east = GeoPoint(lat=north, lon=east)
    return haversine_m(south_west, north_east) / 2

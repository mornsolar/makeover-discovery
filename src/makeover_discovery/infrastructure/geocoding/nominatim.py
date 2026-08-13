"""Nominatim geocoder.

Two behaviours here are dictated by reality rather than preference:

* Nominatim's usage policy requires an identifying ``User-Agent`` and allows
  about one request per second, so this adapter is useless without the rate
  limiter and cache injected into it.
* Postcode boundaries in OpenStreetMap are patchy - Malaysian ones especially -
  so a structured postcode lookup is tried first, then a free-text one, and a
  point plus radius is accepted when no boundary polygon comes back at all.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Final

from makeover_contracts.geo import (
    MAX_SEARCH_RADIUS_M,
    MIN_POLYGON_VERTICES,
    MIN_SEARCH_RADIUS_M,
    CircleArea,
    GeoArea,
    GeoPoint,
    PolygonArea,
    Postcode,
)

from makeover_discovery.domain.model.geo_math import bounding_box_radius_m
from makeover_discovery.infrastructure.http.cached_client import CachedHttpClient

RATE_KEY: Final = "nominatim"
SEARCH_PATH: Final = "/search"
BOUNDING_BOX_VALUES: Final = 4
COORDINATE_PAIR_VALUES: Final = 2

MAX_AREA_VERTICES: Final = 64
"""Cap on the boundary passed downstream.

A real postcode boundary can carry thousands of vertices, and Overpass rejects
a query built from all of them. The ring is thinned to this many, which shifts
the edge by a few metres - immaterial when the result is then filtered by a
provider that is itself only approximately complete.
"""


class NominatimGeocoder:
    """Resolves a postcode to a ``GeoArea`` using OpenStreetMap's geocoder."""

    def __init__(
        self,
        http: CachedHttpClient,
        *,
        base_url: str,
        default_radius_m: float,
        max_radius_m: float,
    ) -> None:
        self._http = http
        self._base_url = base_url.rstrip("/")
        self._default_radius_m = default_radius_m
        self._max_radius_m = max_radius_m

    async def geocode(self, postcode: Postcode) -> GeoArea | None:
        for params in self._query_plan(postcode):
            payload = await self._http.get_json(
                f"{self._base_url}{SEARCH_PATH}",
                params,
                rate_key=RATE_KEY,
            )
            area = self._to_area(payload)
            if area is not None:
                return area
        return None

    def _query_plan(self, postcode: Postcode) -> tuple[Mapping[str, str], ...]:
        """Structured lookup first, free text second.

        The structured form is precise but only matches postcodes that carry a
        dedicated ``postal_code`` object. The free-text form is looser and will
        often match a place whose address merely mentions the code - acceptable
        as a fallback, wrong as a first choice.
        """
        common = {
            "format": "jsonv2",
            "polygon_geojson": "1",
            "limit": "1",
            "countrycodes": postcode.country.lower(),
        }
        return (
            {**common, "postalcode": postcode.value},
            {**common, "q": postcode.value},
        )

    def _to_area(self, payload: Any) -> GeoArea | None:
        if not isinstance(payload, list) or not payload:
            return None
        first = payload[0]
        if not isinstance(first, dict):
            return None

        polygon = _polygon_from(first.get("geojson"))
        if polygon is not None:
            return polygon
        return self._circle_from(first)

    def _circle_from(self, entry: Mapping[str, Any]) -> CircleArea | None:
        center = _point_from(entry.get("lat"), entry.get("lon"))
        if center is None:
            return None
        radius = _radius_from_bounding_box(entry.get("boundingbox")) or self._default_radius_m
        # Nominatim synthesises a generous box around a postcode *point*, so
        # the half-diagonal can be several kilometres for a district a few
        # streets wide. Trusting it un-capped drags in neighbouring postcodes.
        ceiling = min(self._max_radius_m, MAX_SEARCH_RADIUS_M)
        clamped = min(max(radius, MIN_SEARCH_RADIUS_M), ceiling)
        return CircleArea(center=center, radius_m=clamped)


def _point_from(lat: Any, lon: Any) -> GeoPoint | None:
    try:
        return GeoPoint(lat=float(lat), lon=float(lon))
    except (TypeError, ValueError):
        return None


def _radius_from_bounding_box(raw: Any) -> float | None:
    if not isinstance(raw, list) or len(raw) != BOUNDING_BOX_VALUES:
        return None
    try:
        south, north, west, east = (float(value) for value in raw)
    except (TypeError, ValueError):
        return None
    return bounding_box_radius_m(south, north, west, east)


def _polygon_from(geojson: Any) -> PolygonArea | None:
    ring = _outer_ring(geojson)
    if ring is None:
        return None
    vertices = _thin(_drop_closing_vertex(ring))
    if len(vertices) < MIN_POLYGON_VERTICES:
        return None
    return PolygonArea(vertices=vertices)


def _outer_ring(geojson: Any) -> tuple[GeoPoint, ...] | None:
    """Extract the outer ring of a GeoJSON Polygon or MultiPolygon.

    For a MultiPolygon only the first polygon is used. Postcodes split across
    disjoint parts are rare, and a search area that covers the largest part is
    a better answer than refusing to search at all.
    """
    if not isinstance(geojson, dict):
        return None
    coordinates = geojson.get("coordinates")
    kind = geojson.get("type")
    if kind == "MultiPolygon":
        if not isinstance(coordinates, list) or not coordinates:
            return None
        coordinates = coordinates[0]
    elif kind != "Polygon":
        return None

    if not isinstance(coordinates, list) or not coordinates:
        return None
    return _to_points(coordinates[0])


def _to_points(raw_ring: Any) -> tuple[GeoPoint, ...] | None:
    if not isinstance(raw_ring, list):
        return None
    points: list[GeoPoint] = []
    for pair in raw_ring:
        if not isinstance(pair, list | tuple) or len(pair) < COORDINATE_PAIR_VALUES:
            return None
        # GeoJSON is longitude-first; getting this backwards puts Kuala Lumpur
        # in the Indian Ocean, so it is worth stating explicitly.
        point = _point_from(pair[1], pair[0])
        if point is None:
            return None
        points.append(point)
    return tuple(points)


def _drop_closing_vertex(ring: Sequence[GeoPoint]) -> tuple[GeoPoint, ...]:
    if len(ring) > 1 and ring[0] == ring[-1]:
        return tuple(ring[:-1])
    return tuple(ring)


def _thin(ring: tuple[GeoPoint, ...]) -> tuple[GeoPoint, ...]:
    if len(ring) <= MAX_AREA_VERTICES:
        return ring
    stride = -(-len(ring) // MAX_AREA_VERTICES)
    return tuple(ring[::stride])

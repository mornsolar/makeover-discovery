"""Google Places business directory.

Optional and off by default: OpenStreetMap is the primary, no-key source, and
this adapter exists behind the same ``BusinessDirectory`` port for callers who
have a Places API key and want its (often more current) coverage instead.

Every candidate this returns carries ``DataLicense.GOOGLE_PLACES_TOS`` and is
built through ``RetentionPolicy``, which stamps the 30-day caching limit the
Places terms impose - the same mechanism that gives OpenStreetMap data no
limit at all, decided in one place rather than reimplemented per adapter.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any, Final

from makeover_contracts.business import BusinessCandidate
from makeover_contracts.geo import CircleArea, GeoArea, GeoPoint, PolygonArea
from makeover_contracts.provenance import DataLicense, DataSource

from makeover_discovery.application.ports.clock import Clock
from makeover_discovery.domain.errors import UpstreamError
from makeover_discovery.domain.model.discovery import SearchFilters
from makeover_discovery.domain.model.geo_math import polygon_radius_m
from makeover_discovery.domain.policy.retention import RetentionPolicy
from makeover_discovery.infrastructure.directory.places_taxonomy import (
    classify,
    included_types_for,
)
from makeover_discovery.infrastructure.http.cached_client import CachedHttpClient

RATE_KEY: Final = "google_places"
SEARCH_PATH: Final = "/places:searchNearby"

MAX_RESULT_COUNT: Final = 20
"""Places' own ceiling on ``maxResultCount``. Unlike Overpass, this is a hard
API limit, not a tunable we chose - a request above it is simply rejected."""

FIELD_MASK: Final = ",".join(
    (
        "places.id",
        "places.displayName",
        "places.primaryType",
        "places.types",
        "places.location",
        "places.formattedAddress",
        "places.websiteUri",
    )
)
"""Places bills per field requested; this lists exactly what the candidate
model uses, both to keep cost down and to keep the response mapping honest."""

MAX_NAME_CHARS: Final = 200
MAX_ADDRESS_CHARS: Final = 300
MAX_URL_CHARS: Final = 2048


class GooglePlacesDirectory:
    """Searches Google Places for businesses inside a ``GeoArea``."""

    def __init__(
        self,
        http: CachedHttpClient,
        clock: Clock,
        *,
        base_url: str,
        api_key: str,
        retention: RetentionPolicy,
    ) -> None:
        self._http = http
        self._clock = clock
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._retention = retention

    async def search(
        self,
        area: GeoArea,
        filters: SearchFilters,
    ) -> tuple[BusinessCandidate, ...]:
        payload = await self._http.post_json(
            f"{self._base_url}{SEARCH_PATH}",
            build_request(area, filters),
            rate_key=RATE_KEY,
            headers={"X-Goog-Api-Key": self._api_key, "X-Goog-FieldMask": FIELD_MASK},
        )
        return self._to_candidates(payload)

    def _to_candidates(self, payload: Any) -> tuple[BusinessCandidate, ...]:
        if not isinstance(payload, dict):
            raise UpstreamError("Google Places returned a payload that is not an object")
        places = payload.get("places", [])
        if not isinstance(places, list):
            raise UpstreamError("Google Places response has a non-list 'places' field")

        fetched_at = self._clock.now()
        candidates = (self._to_candidate(place, fetched_at) for place in places)
        return tuple(candidate for candidate in candidates if candidate is not None)

    def _to_candidate(self, place: Any, fetched_at: datetime) -> BusinessCandidate | None:
        if not isinstance(place, dict):
            return None
        place_id = place.get("id")
        name = _display_name(place)
        location = _location_of(place)
        types = place.get("types")
        category = classify(types if isinstance(types, list) else [])

        if not isinstance(place_id, str) or name is None or location is None or category is None:
            return None

        return BusinessCandidate(
            external_id=place_id,
            name=name,
            category=category,
            location=location,
            address_line=_clean(place.get("formattedAddress"), MAX_ADDRESS_CHARS),
            website=_clean(place.get("websiteUri"), MAX_URL_CHARS),
            source=self._retention.build_source_ref(
                source=DataSource.GOOGLE_PLACES,
                data_license=DataLicense.GOOGLE_PLACES_TOS,
                fetched_at=fetched_at,
                source_id=place_id,
            ),
        )


def build_request(area: GeoArea, filters: SearchFilters) -> dict[str, Any]:
    """Render the ``searchNearby`` JSON body for one search.

    Module-level so the request shape can be asserted on without an adapter or
    an HTTP client.
    """
    center = area.query_center
    return {
        "locationRestriction": {
            "circle": {
                "center": {"latitude": center.lat, "longitude": center.lon},
                "radius": _radius_for(area),
            }
        },
        "includedTypes": list(included_types_for(filters.categories)),
        "maxResultCount": min(filters.limit, MAX_RESULT_COUNT),
    }


def _radius_for(area: GeoArea) -> float:
    if isinstance(area, CircleArea):
        return area.radius_m
    return _polygon_radius_clamped(area)


def _polygon_radius_clamped(area: PolygonArea) -> float:
    # Places rejects a radius outside (0, 50000] metres; a polygon derived
    # from a very large postcode boundary could otherwise exceed that.
    return min(polygon_radius_m(area), 50_000.0)


def _display_name(place: Mapping[str, Any]) -> str | None:
    display = place.get("displayName")
    text = display.get("text") if isinstance(display, dict) else None
    return _clean(text, MAX_NAME_CHARS)


def _location_of(place: Mapping[str, Any]) -> GeoPoint | None:
    location = place.get("location")
    if not isinstance(location, dict):
        return None
    try:
        return GeoPoint(lat=float(location["latitude"]), lon=float(location["longitude"]))
    except (TypeError, ValueError, KeyError):
        return None


def _clean(raw: Any, max_chars: int) -> str | None:
    if not isinstance(raw, str):
        return None
    collapsed = " ".join(raw.split())
    return collapsed[:max_chars] or None

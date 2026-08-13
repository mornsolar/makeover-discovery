"""Overpass business directory.

Overpass answers "what is tagged inside this area" against live OpenStreetMap
data. Everything it returns is ODbL, so every candidate leaves this adapter
carrying a ``SourceRef`` that says so - the landing page's attribution is then
derived rather than remembered.
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
from makeover_discovery.domain.policy.retention import RetentionPolicy
from makeover_discovery.infrastructure.directory.osm_taxonomy import classify, selectors_for
from makeover_discovery.infrastructure.http.cached_client import CachedHttpClient

RATE_KEY: Final = "overpass"
INTERPRETER_PATH: Final = "/interpreter"
OSM_BROWSE_URL: Final = "https://www.openstreetmap.org"

QUERY_TIMEOUT_S: Final = 25
"""Server-side budget. Overpass aborts and returns an error past this, which
surfaces as an ``UpstreamError`` rather than a silently partial answer."""

MAX_NAME_CHARS: Final = 200
MAX_ADDRESS_CHARS: Final = 300
MAX_URL_CHARS: Final = 2048
MAX_EXTERNAL_ID_CHARS: Final = 128

_CENTRED_TYPES: Final = frozenset({"way", "relation"})


class OverpassDirectory:
    """Searches OpenStreetMap for businesses inside a ``GeoArea``."""

    def __init__(
        self,
        http: CachedHttpClient,
        clock: Clock,
        *,
        base_url: str,
        retention: RetentionPolicy,
    ) -> None:
        self._http = http
        self._clock = clock
        self._base_url = base_url.rstrip("/")
        self._retention = retention

    async def search(
        self,
        area: GeoArea,
        filters: SearchFilters,
    ) -> tuple[BusinessCandidate, ...]:
        query = build_query(area, filters)
        payload = await self._http.post_form_json(
            f"{self._base_url}{INTERPRETER_PATH}",
            {"data": query},
            rate_key=RATE_KEY,
        )
        return self._to_candidates(payload)

    def _to_candidates(self, payload: Any) -> tuple[BusinessCandidate, ...]:
        if not isinstance(payload, dict):
            raise UpstreamError("Overpass returned a payload that is not an object")
        elements = payload.get("elements")
        if not isinstance(elements, list):
            raise UpstreamError("Overpass response is missing an 'elements' list")

        fetched_at = self._clock.now()
        candidates = (self._to_candidate(element, fetched_at) for element in elements)
        return tuple(candidate for candidate in candidates if candidate is not None)

    def _to_candidate(self, element: Any, fetched_at: datetime) -> BusinessCandidate | None:
        if not isinstance(element, dict):
            return None
        tags = element.get("tags")
        if not isinstance(tags, dict):
            return None

        name = _clean(tags.get("name"), MAX_NAME_CHARS)
        category = classify(tags)
        location = _location_of(element)
        external_id = _external_id(element)
        if name is None or category is None or location is None or external_id is None:
            # An unnamed or unplaceable feature cannot be shown to a user or
            # rendered, so it is dropped rather than filled in with a guess.
            return None

        return BusinessCandidate(
            external_id=external_id,
            name=name,
            category=category,
            location=location,
            address_line=_address_line(tags),
            website=_website(tags),
            # ODbL imposes share-alike rather than a retention window, but the
            # policy decides that, not this adapter.
            source=self._retention.build_source_ref(
                source=DataSource.OPENSTREETMAP,
                data_license=DataLicense.ODBL_1_0,
                fetched_at=fetched_at,
                source_id=external_id,
                url=f"{OSM_BROWSE_URL}/{external_id}",
            ),
        )


def build_query(area: GeoArea, filters: SearchFilters) -> str:
    """Render the Overpass QL for one search.

    Kept a module-level function so the generated query can be asserted on
    directly, without standing up an adapter or an HTTP client.

    Note what is *absent*: any element limit. Overpass has no notion of
    distance from a point, so its ``out`` limit truncates by quadtile - a
    spatial ordering that, measured against live Kuala Lumpur data, returned
    a slice whose nearest business was 1.2 km from the search centre while
    the true nearest was 77 m away. There is no server-side cap that answers
    "the ten nearest", so the whole area is fetched and ranked here.

    The area is therefore what bounds the response: circles are capped by
    ``max_search_radius_m`` at geocode time, and an over-large polygon is
    rejected by Overpass's own timeout rather than by us.
    """
    spatial = _spatial_filter(area)
    statements = "".join(
        f"  nwr{selector}{spatial};\n" for selector in selectors_for(filters.categories)
    )
    return f"[out:json][timeout:{QUERY_TIMEOUT_S}];\n(\n{statements});\nout tags center qt;\n"


def _spatial_filter(area: GeoArea) -> str:
    if isinstance(area, CircleArea):
        center = area.center
        return f"(around:{area.radius_m:.0f},{center.lat:.6f},{center.lon:.6f})"
    return _polygon_filter(area)


def _polygon_filter(area: PolygonArea) -> str:
    # Overpass wants a flat, space-separated "lat lon lat lon" string.
    points = " ".join(f"{vertex.lat:.6f} {vertex.lon:.6f}" for vertex in area.vertices)
    return f'(poly:"{points}")'


def _location_of(element: Mapping[str, Any]) -> GeoPoint | None:
    if element.get("type") in _CENTRED_TYPES:
        center = element.get("center")
        if not isinstance(center, dict):
            return None
        return _point(center.get("lat"), center.get("lon"))
    return _point(element.get("lat"), element.get("lon"))


def _point(lat: Any, lon: Any) -> GeoPoint | None:
    try:
        return GeoPoint(lat=float(lat), lon=float(lon))
    except (TypeError, ValueError):
        return None


def _external_id(element: Mapping[str, Any]) -> str | None:
    kind = element.get("type")
    identifier = element.get("id")
    if not isinstance(kind, str) or not isinstance(identifier, int):
        return None
    return _clean(f"{kind}/{identifier}", MAX_EXTERNAL_ID_CHARS)


def _address_line(tags: Mapping[str, Any]) -> str | None:
    street = " ".join(
        part
        for part in (tags.get("addr:housenumber"), tags.get("addr:street"))
        if isinstance(part, str) and part.strip()
    )
    parts = (street, tags.get("addr:city"), tags.get("addr:postcode"))
    joined = ", ".join(part for part in parts if isinstance(part, str) and part.strip())
    return _clean(joined, MAX_ADDRESS_CHARS)


def _website(tags: Mapping[str, Any]) -> str | None:
    raw = tags.get("website") or tags.get("contact:website")
    if not isinstance(raw, str) or not raw.lower().startswith(("http://", "https://")):
        # OpenStreetMap holds plenty of bare domains and even phone numbers in
        # this tag; anything we cannot safely turn into a link is discarded.
        return None
    return _clean(raw, MAX_URL_CHARS)


def _clean(raw: Any, max_chars: int) -> str | None:
    if not isinstance(raw, str):
        return None
    collapsed = " ".join(raw.split())
    if not collapsed:
        return None
    return collapsed[:max_chars]

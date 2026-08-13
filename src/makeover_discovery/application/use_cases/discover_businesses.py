"""Discover businesses near a postcode."""

from __future__ import annotations

from makeover_contracts.business import BusinessCandidate
from makeover_contracts.geo import GeoArea

from makeover_discovery.application.ports.business_directory import BusinessDirectory
from makeover_discovery.application.ports.geocoder import Geocoder
from makeover_discovery.domain.errors import NotFoundError
from makeover_discovery.domain.model.dedupe import deduplicate
from makeover_discovery.domain.model.discovery import DiscoveryQuery, DiscoveryResult
from makeover_discovery.domain.model.geo_math import haversine_m


class DiscoverBusinesses:
    """Postcode in, ranked and de-duplicated candidates out.

    Depends only on the two ports, so the same use case serves live
    OpenStreetMap, a Google Places adapter, or a fixture file with no change.
    """

    def __init__(self, geocoder: Geocoder, directory: BusinessDirectory) -> None:
        self._geocoder = geocoder
        self._directory = directory

    async def execute(self, query: DiscoveryQuery) -> DiscoveryResult:
        area = await self._geocoder.geocode(query.postcode)
        if area is None:
            raise NotFoundError(f"no area found for postcode {query.postcode}")

        found = await self._directory.search(area, query.filters)
        ranked = _rank(deduplicate(found), area)
        return DiscoveryResult.build(query.postcode, area, ranked[: query.filters.limit])


def _rank(
    candidates: tuple[BusinessCandidate, ...],
    area: GeoArea,
) -> tuple[BusinessCandidate, ...]:
    """Nearest to the area's centre first.

    ``external_id`` breaks ties so that two runs over the same data return the
    same order. Without it, a cached response and a fresh one could disagree
    about which business is "first", which would later mean two different
    renders for the same postcode.
    """
    center = area.query_center
    return tuple(
        sorted(
            candidates,
            key=lambda candidate: (haversine_m(center, candidate.location), candidate.external_id),
        )
    )

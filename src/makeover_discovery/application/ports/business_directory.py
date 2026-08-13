"""Business directory port."""

from __future__ import annotations

from typing import Protocol

from makeover_contracts.business import BusinessCandidate
from makeover_contracts.geo import GeoArea

from makeover_discovery.domain.model.discovery import SearchFilters


class BusinessDirectory(Protocol):
    """Finds businesses inside an area.

    Takes a ``GeoArea`` rather than a postcode so that OpenStreetMap, Google
    Places, or a fixture file can all sit behind the same port.
    """

    async def search(
        self,
        area: GeoArea,
        filters: SearchFilters,
    ) -> tuple[BusinessCandidate, ...]:
        """Return candidates within ``area``, each carrying its own source."""
        ...

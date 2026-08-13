"""Hand-written ``BusinessDirectory`` fake."""

from __future__ import annotations

from makeover_contracts.business import BusinessCandidate
from makeover_contracts.geo import GeoArea

from makeover_discovery.domain.model.discovery import SearchFilters


class FakeBusinessDirectory:
    """Returns a fixed list, recording the area and filters it was given."""

    def __init__(self, candidates: tuple[BusinessCandidate, ...] = ()) -> None:
        self._candidates = candidates
        self.calls: list[tuple[GeoArea, SearchFilters]] = []

    async def search(
        self,
        area: GeoArea,
        filters: SearchFilters,
    ) -> tuple[BusinessCandidate, ...]:
        self.calls.append((area, filters))
        return self._candidates

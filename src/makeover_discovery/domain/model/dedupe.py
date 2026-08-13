"""Candidate de-duplication.

OpenStreetMap frequently carries the same business twice - once as a node for
the point of interest and once as a way for the building it occupies - so a
single Overpass response can contain visible duplicates. Any provider that
merges multiple upstreams will hit the same problem, so the rule lives here
rather than inside one adapter.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final

from makeover_contracts.business import BusinessCandidate

COORDINATE_PRECISION: Final = 4
"""Decimal places of latitude/longitude treated as "the same spot" (~11 m).

Deliberately conservative. Merging two genuinely different shops is a visible
wrong answer; leaving a duplicate in the list is merely untidy.
"""


def _identity(candidate: BusinessCandidate) -> tuple[str, float, float]:
    normalised_name = " ".join(candidate.name.split()).casefold()
    return (
        normalised_name,
        round(candidate.location.lat, COORDINATE_PRECISION),
        round(candidate.location.lon, COORDINATE_PRECISION),
    )


def deduplicate(candidates: Iterable[BusinessCandidate]) -> tuple[BusinessCandidate, ...]:
    """Keep the first candidate seen for each name-and-place, preserving order."""
    kept: dict[tuple[str, float, float], BusinessCandidate] = {}
    for candidate in candidates:
        kept.setdefault(_identity(candidate), candidate)
    return tuple(kept.values())

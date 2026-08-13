"""Geocoding port."""

from __future__ import annotations

from typing import Protocol

from makeover_contracts.geo import GeoArea, Postcode


class Geocoder(Protocol):
    """Turns a postcode into a searchable area."""

    async def geocode(self, postcode: Postcode) -> GeoArea | None:
        """Return the area a postcode covers, or ``None`` if it is unknown.

        ``None`` rather than an exception: "this postcode is not in the
        provider" is an ordinary outcome, and the decision to treat it as a 404
        belongs to the use case, not to an adapter.
        """
        ...

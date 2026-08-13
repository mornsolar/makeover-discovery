"""Hand-written ``Geocoder`` fakes.

Fakes rather than mocks: the ports are Protocols, so a real class satisfies
them structurally, and a fake that must actually behave catches contract drift
that a configured mock would happily hide.
"""

from __future__ import annotations

from makeover_contracts.geo import CircleArea, GeoArea, GeoPoint, Postcode

from makeover_discovery.domain.errors import UpstreamError

KUALA_LUMPUR = CircleArea(center=GeoPoint(lat=3.16, lon=101.71), radius_m=1500.0)


class FakeGeocoder:
    """Resolves postcodes from a lookup table and records what it was asked."""

    def __init__(self, areas: dict[str, GeoArea] | None = None) -> None:
        self._areas = areas if areas is not None else {"50450 MY": KUALA_LUMPUR}
        self.calls: list[Postcode] = []

    async def geocode(self, postcode: Postcode) -> GeoArea | None:
        self.calls.append(postcode)
        return self._areas.get(str(postcode))


class FailingGeocoder:
    """Always reports the provider as unreachable."""

    async def geocode(self, postcode: Postcode) -> GeoArea | None:
        raise UpstreamError(f"geocoder unavailable for {postcode}")

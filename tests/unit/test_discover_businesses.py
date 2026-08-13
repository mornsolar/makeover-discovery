"""The discovery use case."""

from __future__ import annotations

import pytest
from makeover_contracts.business import BusinessCategory
from makeover_contracts.geo import Postcode

from makeover_discovery.application.use_cases.discover_businesses import DiscoverBusinesses
from makeover_discovery.domain.errors import NotFoundError
from makeover_discovery.domain.model.discovery import DiscoveryQuery, SearchFilters
from tests.fakes.candidates import make_candidate
from tests.fakes.directory import FakeBusinessDirectory
from tests.fakes.geocoder import KUALA_LUMPUR, FakeGeocoder

POSTCODE = Postcode(value="50450", country="MY")
UNKNOWN_POSTCODE = Postcode(value="99999", country="MY")


def build(candidates=(), **filter_kwargs) -> tuple[DiscoverBusinesses, DiscoveryQuery]:
    use_case = DiscoverBusinesses(FakeGeocoder(), FakeBusinessDirectory(candidates))
    query = DiscoveryQuery(postcode=POSTCODE, filters=SearchFilters(**filter_kwargs))
    return use_case, query


async def test_raises_when_the_postcode_cannot_be_located():
    use_case, _ = build()
    query = DiscoveryQuery(postcode=UNKNOWN_POSTCODE)

    with pytest.raises(NotFoundError, match="99999"):
        await use_case.execute(query)


async def test_does_not_search_when_geocoding_fails():
    directory = FakeBusinessDirectory()
    use_case = DiscoverBusinesses(FakeGeocoder(), directory)

    with pytest.raises(NotFoundError):
        await use_case.execute(DiscoveryQuery(postcode=UNKNOWN_POSTCODE))

    assert directory.calls == []


async def test_returns_the_nearest_business_first():
    far = make_candidate(external_id="node/far", name="Far", lat=3.1800, lon=101.7300)
    near = make_candidate(external_id="node/near", name="Near", lat=3.1601, lon=101.7101)
    use_case, query = build((far, near))

    result = await use_case.execute(query)

    assert [candidate.name for candidate in result.candidates] == ["Near", "Far"]


async def test_orders_equidistant_businesses_by_stable_identifier():
    # Two candidates at the same point must not be ordered by whatever the
    # provider happened to return, or a cached run and a fresh run would
    # disagree about which business gets rendered.
    first = make_candidate(external_id="node/1", name="Alpha")
    second = make_candidate(external_id="node/2", name="Beta")
    use_case, query = build((second, first))

    result = await use_case.execute(query)

    assert [candidate.external_id for candidate in result.candidates] == ["node/1", "node/2"]


async def test_removes_duplicates_before_applying_the_limit():
    node = make_candidate(external_id="node/1")
    way = make_candidate(external_id="way/1")
    other = make_candidate(external_id="node/2", name="Other", lat=3.1610)
    use_case, query = build((node, way, other), limit=2)

    result = await use_case.execute(query)

    assert len(result.candidates) == 2
    assert {candidate.name for candidate in result.candidates} == {"Kedai Kopi Ali", "Other"}


async def test_truncates_to_the_requested_limit():
    candidates = tuple(
        make_candidate(external_id=f"node/{index}", name=f"Shop {index}", lat=3.16 + index / 1000)
        for index in range(5)
    )
    use_case, query = build(candidates, limit=2)

    result = await use_case.execute(query)

    assert len(result.candidates) == 2


async def test_passes_the_geocoded_area_and_filters_to_the_directory():
    directory = FakeBusinessDirectory()
    use_case = DiscoverBusinesses(FakeGeocoder(), directory)
    filters = SearchFilters(categories=(BusinessCategory.CAFE,), limit=3)

    await use_case.execute(DiscoveryQuery(postcode=POSTCODE, filters=filters))

    assert directory.calls == [(KUALA_LUMPUR, filters)]


async def test_reports_the_attribution_the_results_oblige():
    use_case, query = build((make_candidate(),))

    result = await use_case.execute(query)

    assert result.attributions == ("© OpenStreetMap contributors",)

"""Discovery query and result models."""

from __future__ import annotations

import pytest
from makeover_contracts.business import BusinessCategory
from makeover_contracts.geo import Postcode
from makeover_contracts.provenance import DataLicense, DataSource, SourceRef
from pydantic import ValidationError

from makeover_discovery.domain.model.discovery import (
    MAX_RESULT_LIMIT,
    DiscoveryResult,
    SearchFilters,
)
from tests.fakes.candidates import FETCHED_AT, make_candidate
from tests.fakes.geocoder import KUALA_LUMPUR

POSTCODE = Postcode(value="50450", country="MY")


def test_drops_duplicate_categories_but_keeps_order():
    filters = SearchFilters(
        categories=(BusinessCategory.CAFE, BusinessCategory.BAKERY, BusinessCategory.CAFE)
    )

    assert filters.categories == (BusinessCategory.CAFE, BusinessCategory.BAKERY)


def test_rejects_a_limit_above_the_ceiling():
    with pytest.raises(ValidationError):
        SearchFilters(limit=MAX_RESULT_LIMIT + 1)


def test_defaults_to_every_category():
    assert SearchFilters().categories == ()


def test_derives_attribution_from_candidate_licences():
    result = DiscoveryResult.build(POSTCODE, KUALA_LUMPUR, (make_candidate(),))

    assert result.attributions == ("© OpenStreetMap contributors",)


def test_reports_each_attribution_once():
    candidates = (make_candidate(external_id="node/1"), make_candidate(external_id="node/2"))

    result = DiscoveryResult.build(POSTCODE, KUALA_LUMPUR, candidates)

    assert result.attributions == ("© OpenStreetMap contributors",)


def test_omits_licences_that_require_no_credit():
    unattributed = make_candidate(
        source=SourceRef(
            source=DataSource.MANUAL_UPLOAD,
            license=DataLicense.USER_PROVIDED,
            fetched_at=FETCHED_AT,
        )
    )

    result = DiscoveryResult.build(POSTCODE, KUALA_LUMPUR, (unattributed,))

    assert result.attributions == ()


def test_has_no_attribution_without_candidates():
    result = DiscoveryResult.build(POSTCODE, KUALA_LUMPUR, ())

    assert result.attributions == ()
    assert result.candidates == ()

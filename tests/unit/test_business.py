from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from makeover_contracts.business import BusinessCategory, BusinessProfile
from makeover_contracts.geo import GeoPoint
from makeover_contracts.provenance import (
    DataLicense,
    DataSource,
    Provenanced,
    SourceRef,
)
from pydantic import ValidationError

FETCHED_AT = datetime(2026, 8, 13, 9, 0, tzinfo=UTC)

OSM = SourceRef(
    source=DataSource.OPENSTREETMAP,
    license=DataLicense.ODBL_1_0,
    fetched_at=FETCHED_AT,
)
PLACES = SourceRef(
    source=DataSource.GOOGLE_PLACES,
    license=DataLicense.GOOGLE_PLACES_TOS,
    fetched_at=FETCHED_AT,
    retention_until=FETCHED_AT + timedelta(days=30),
)
OWN_SITE = SourceRef(
    source=DataSource.BUSINESS_WEBSITE,
    license=DataLicense.PUBLICLY_PUBLISHED,
    fetched_at=FETCHED_AT,
)


def make_profile(**overrides) -> BusinessProfile:
    defaults = {
        "id": "kedai-kopi-50450",
        "name": Provenanced(value="Kedai Kopi Bukit", source=OSM),
        "category": Provenanced(value=BusinessCategory.CAFE, source=OSM),
        "location": Provenanced(value=GeoPoint(lat=3.1578, lon=101.7117), source=OSM),
    }
    return BusinessProfile(**{**defaults, **overrides})


class TestAttributions:
    def test_collects_one_entry_per_distinct_licence(self):
        profile = make_profile(website=Provenanced(value="https://example.my", source=OSM))
        assert profile.attributions() == ("© OpenStreetMap contributors",)

    def test_includes_google_attribution_when_places_contributed(self):
        profile = make_profile(phone=Provenanced(value="+60312345678", source=PLACES))
        assert set(profile.attributions()) == {
            "© OpenStreetMap contributors",
            "Powered by Google",
        }

    def test_omits_licences_that_require_no_attribution(self):
        profile = make_profile(descriptors=(Provenanced(value="outdoor seating", source=OWN_SITE),))
        assert profile.attributions() == ("© OpenStreetMap contributors",)

    def test_walks_into_collection_fields(self):
        profile = make_profile(
            photo_urls=(Provenanced(value="https://example.my/a.jpg", source=PLACES),)
        )
        assert "Powered by Google" in profile.attributions()


class TestRetention:
    def test_reports_nothing_expired_inside_the_window(self):
        profile = make_profile(phone=Provenanced(value="+60312345678", source=PLACES))
        assert profile.expired_fields(FETCHED_AT + timedelta(days=29)) == ()

    def test_reports_the_field_path_once_expired(self):
        profile = make_profile(phone=Provenanced(value="+60312345678", source=PLACES))
        assert profile.expired_fields(FETCHED_AT + timedelta(days=31)) == ("phone",)

    def test_indexes_expired_entries_inside_collections(self):
        profile = make_profile(
            photo_urls=(
                Provenanced(value="https://example.my/a.jpg", source=OSM),
                Provenanced(value="https://example.my/b.jpg", source=PLACES),
            )
        )
        assert profile.expired_fields(FETCHED_AT + timedelta(days=31)) == ("photo_urls[1]",)


class TestProfileConstruction:
    def test_rejects_an_id_that_is_not_a_slug(self):
        with pytest.raises(ValidationError):
            make_profile(id="Kedai Kopi!")

    def test_rejects_unknown_fields(self):
        with pytest.raises(ValidationError):
            make_profile(rating=4.5)

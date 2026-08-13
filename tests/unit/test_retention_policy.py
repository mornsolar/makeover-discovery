"""Retention windows by source."""

from __future__ import annotations

from datetime import timedelta

from makeover_contracts.provenance import DataLicense, DataSource

from makeover_discovery.domain.policy.retention import (
    GOOGLE_PLACES_RETENTION_DAYS,
    RetentionPolicy,
)
from tests.fakes.candidates import FETCHED_AT

policy = RetentionPolicy()


def test_openstreetmap_data_has_no_deadline():
    ref = policy.build_source_ref(
        source=DataSource.OPENSTREETMAP,
        data_license=DataLicense.ODBL_1_0,
        fetched_at=FETCHED_AT,
    )

    assert ref.retention_until is None


def test_places_data_expires_within_the_permitted_window():
    # The Places terms cap caching at 30 days; a field that outlives that is a
    # licence breach, so the deadline is stamped on at capture time.
    ref = policy.build_source_ref(
        source=DataSource.GOOGLE_PLACES,
        data_license=DataLicense.GOOGLE_PLACES_TOS,
        fetched_at=FETCHED_AT,
    )

    assert ref.retention_until == FETCHED_AT + timedelta(days=GOOGLE_PLACES_RETENTION_DAYS)


def test_a_places_field_is_not_expired_on_the_day_it_was_fetched():
    ref = policy.build_source_ref(
        source=DataSource.GOOGLE_PLACES,
        data_license=DataLicense.GOOGLE_PLACES_TOS,
        fetched_at=FETCHED_AT,
    )

    assert not ref.is_expired(FETCHED_AT + timedelta(days=29))
    assert ref.is_expired(FETCHED_AT + timedelta(days=30))


def test_published_website_content_has_no_deadline():
    assert policy.window_for(DataSource.BUSINESS_WEBSITE) is None


def test_carries_the_source_identity_through():
    ref = policy.build_source_ref(
        source=DataSource.OPENSTREETMAP,
        data_license=DataLicense.ODBL_1_0,
        fetched_at=FETCHED_AT,
        source_id="node/1",
        url="https://www.openstreetmap.org/node/1",
    )

    assert ref.source_id == "node/1"
    assert ref.attribution == "© OpenStreetMap contributors"

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from makeover_contracts.provenance import (
    DataLicense,
    DataSource,
    Provenanced,
    SourceRef,
)
from pydantic import ValidationError

FETCHED_AT = datetime(2026, 8, 13, 9, 0, tzinfo=UTC)


def make_source(**overrides) -> SourceRef:
    defaults = {
        "source": DataSource.OPENSTREETMAP,
        "license": DataLicense.ODBL_1_0,
        "fetched_at": FETCHED_AT,
    }
    return SourceRef(**{**defaults, **overrides})


class TestSourceRef:
    def test_rejects_naive_fetched_at(self):
        with pytest.raises(ValidationError, match="timezone-aware"):
            make_source(fetched_at=datetime(2026, 8, 13, 9, 0))

    def test_rejects_retention_before_fetch(self):
        with pytest.raises(ValidationError, match="must be after fetched_at"):
            make_source(retention_until=FETCHED_AT - timedelta(days=1))

    def test_osm_carries_odbl_attribution(self):
        assert make_source().attribution == "© OpenStreetMap contributors"

    def test_google_places_carries_powered_by_google(self):
        source = make_source(source=DataSource.GOOGLE_PLACES, license=DataLicense.GOOGLE_PLACES_TOS)
        assert source.attribution == "Powered by Google"

    def test_user_provided_needs_no_attribution(self):
        source = make_source(source=DataSource.MANUAL_UPLOAD, license=DataLicense.USER_PROVIDED)
        assert source.attribution is None

    def test_never_expires_without_a_retention_window(self):
        assert make_source().is_expired(FETCHED_AT + timedelta(days=3650)) is False

    def test_expires_once_the_window_closes(self):
        source = make_source(retention_until=FETCHED_AT + timedelta(days=30))
        assert source.is_expired(FETCHED_AT + timedelta(days=29)) is False
        assert source.is_expired(FETCHED_AT + timedelta(days=30)) is True

    def test_rejects_naive_now_when_checking_expiry(self):
        with pytest.raises(ValueError, match="timezone-aware"):
            make_source().is_expired(datetime(2026, 8, 13, 9, 0))


class TestProvenanced:
    def test_binds_a_value_to_its_source(self):
        wrapped: Provenanced[str] = Provenanced(value="Kedai Kopi", source=make_source())
        assert wrapped.value == "Kedai Kopi"

    def test_delegates_expiry_to_its_source(self):
        source = make_source(retention_until=FETCHED_AT + timedelta(days=30))
        wrapped: Provenanced[str] = Provenanced(value="Kedai Kopi", source=source)
        assert wrapped.is_expired(FETCHED_AT + timedelta(days=31)) is True

    def test_cannot_be_constructed_without_a_source(self):
        with pytest.raises(ValidationError):
            Provenanced(value="Kedai Kopi")

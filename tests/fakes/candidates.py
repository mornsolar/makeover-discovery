"""Builders for candidate fixtures.

A helper rather than literals in every test: ``BusinessCandidate`` has six
required fields, and repeating them obscures the one field a given test is
actually about.
"""

from __future__ import annotations

from datetime import UTC, datetime

from makeover_contracts.business import BusinessCandidate, BusinessCategory
from makeover_contracts.geo import GeoPoint
from makeover_contracts.provenance import DataLicense, DataSource, SourceRef

FETCHED_AT = datetime(2026, 8, 13, 9, 30, tzinfo=UTC)


def osm_source(source_id: str = "node/1") -> SourceRef:
    return SourceRef(
        source=DataSource.OPENSTREETMAP,
        license=DataLicense.ODBL_1_0,
        fetched_at=FETCHED_AT,
        source_id=source_id,
        url=f"https://www.openstreetmap.org/{source_id}",
    )


def make_candidate(
    *,
    external_id: str = "node/1",
    name: str = "Kedai Kopi Ali",
    category: BusinessCategory = BusinessCategory.CAFE,
    lat: float = 3.1600,
    lon: float = 101.7100,
    source: SourceRef | None = None,
    address_line: str | None = None,
    website: str | None = None,
) -> BusinessCandidate:
    return BusinessCandidate(
        external_id=external_id,
        name=name,
        category=category,
        location=GeoPoint(lat=lat, lon=lon),
        source=source or osm_source(external_id),
        address_line=address_line,
        website=website,
    )

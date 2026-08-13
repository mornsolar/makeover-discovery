"""How long each source's data may be kept.

Retention is a licence term, not a storage preference, so it is decided in one
place and stamped onto every ``SourceRef`` at the moment of capture. A field
whose window has closed is purged by the sweeper regardless of who fetched it.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Final

from makeover_contracts.provenance import DataLicense, DataSource, SourceRef

GOOGLE_PLACES_RETENTION_DAYS: Final = 30
"""The Places terms permit caching for 30 days, with place IDs exempt.

We do not rely on the exemption: a shorter, uniform window is simpler to prove
correct than a per-field carve-out.
"""

RETENTION_BY_SOURCE: Final[dict[DataSource, timedelta | None]] = {
    DataSource.OPENSTREETMAP: None,
    DataSource.GOOGLE_PLACES: timedelta(days=GOOGLE_PLACES_RETENTION_DAYS),
    DataSource.BUSINESS_WEBSITE: None,
    DataSource.MANUAL_UPLOAD: None,
    DataSource.DERIVED: None,
}
"""``None`` means the licence imposes no time limit.

ODbL and ordinary published web content are share-alike or open-ended; only the
Places terms put a clock on it.
"""


class RetentionPolicy:
    """Stamps captured values with the deadline their licence implies."""

    def window_for(self, source: DataSource) -> timedelta | None:
        return RETENTION_BY_SOURCE.get(source)

    def build_source_ref(
        self,
        *,
        source: DataSource,
        data_license: DataLicense,
        fetched_at: datetime,
        source_id: str | None = None,
        url: str | None = None,
    ) -> SourceRef:
        """Construct a ``SourceRef`` with ``retention_until`` already correct.

        Adapters call this rather than constructing ``SourceRef`` directly, so
        that adding a source with a retention limit cannot be forgotten at one
        of several call sites.
        """
        window = self.window_for(source)
        return SourceRef(
            source=source,
            license=data_license,
            fetched_at=fetched_at,
            source_id=source_id,
            url=url,
            retention_until=fetched_at + window if window is not None else None,
        )

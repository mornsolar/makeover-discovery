"""Provenance tracking.

The compliance rule this package enforces is simple and structural: **no piece
of third-party business data exists in the system without a ``SourceRef``.**
Rather than trusting every call site to remember that, ``Provenanced[T]`` makes
it a type error to carry a value without its source.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DataSource(StrEnum):
    """Where a field originally came from."""

    OPENSTREETMAP = "openstreetmap"
    GOOGLE_PLACES = "google_places"
    BUSINESS_WEBSITE = "business_website"
    MANUAL_UPLOAD = "manual_upload"
    DERIVED = "derived"


class DataLicense(StrEnum):
    """The terms the data arrived under.

    This drives both the attribution rendered on the landing page and the
    retention sweeper, so it is a closed set rather than a free-text field.
    """

    ODBL_1_0 = "odbl-1.0"
    GOOGLE_PLACES_TOS = "google-places-tos"
    PUBLICLY_PUBLISHED = "publicly-published"
    USER_PROVIDED = "user-provided"
    NOT_APPLICABLE = "not-applicable"


ATTRIBUTION_TEXT: Final[dict[DataLicense, str | None]] = {
    DataLicense.ODBL_1_0: "© OpenStreetMap contributors",
    DataLicense.GOOGLE_PLACES_TOS: "Powered by Google",
    DataLicense.PUBLICLY_PUBLISHED: None,
    DataLicense.USER_PROVIDED: None,
    DataLicense.NOT_APPLICABLE: None,
}
"""Attribution a landing page must display when a licence contributed a field."""


class SourceRef(BaseModel):
    """Where a value came from, when, and under what terms."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: DataSource
    license: DataLicense
    fetched_at: datetime = Field(description="Timezone-aware UTC instant of retrieval")
    source_id: str | None = Field(default=None, max_length=256)
    url: str | None = Field(default=None, max_length=2048)
    retention_until: datetime | None = Field(
        default=None,
        description="Instant after which this value must be purged. None means no limit.",
    )

    @field_validator("fetched_at", "retention_until")
    @classmethod
    def _require_timezone(cls, value: datetime | None) -> datetime | None:
        # A naive datetime silently means "some unknown timezone", which makes
        # retention arithmetic wrong in a way that stays invisible until audit.
        if value is not None and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _retention_must_follow_fetch(self) -> SourceRef:
        if self.retention_until is not None and self.retention_until <= self.fetched_at:
            raise ValueError("retention_until must be after fetched_at")
        return self

    @property
    def attribution(self) -> str | None:
        """Text that must appear wherever this value is displayed, if any."""
        return ATTRIBUTION_TEXT[self.license]

    def is_expired(self, now: datetime) -> bool:
        """Whether this value is past its permitted retention window."""
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        return self.retention_until is not None and now >= self.retention_until


class Provenanced[T](BaseModel):
    """A value bound to the source that supplied it.

    Not frozen, because ``T`` is not guaranteed hashable.
    """

    model_config = ConfigDict(extra="forbid")

    value: T
    source: SourceRef

    def is_expired(self, now: datetime) -> bool:
        return self.source.is_expired(now)

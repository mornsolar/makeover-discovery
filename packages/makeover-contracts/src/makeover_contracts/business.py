"""Business entities.

``BusinessCandidate`` is the cheap result of a directory search; enriching it
with permitted public information produces a ``BusinessProfile``, where every
third-party field carries its own ``SourceRef``.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from makeover_contracts.geo import GeoPoint
from makeover_contracts.primitives import Slug
from makeover_contracts.provenance import Provenanced, SourceRef

MAX_DESCRIPTORS = 12
MAX_PHOTOS = 8


class BusinessCategory(StrEnum):
    """Coarse category, chosen to map onto render templates rather than to
    mirror the full OpenStreetMap tag vocabulary."""

    RESTAURANT = "restaurant"
    CAFE = "cafe"
    BAKERY = "bakery"
    BAR = "bar"
    RETAIL = "retail"
    SALON = "salon"
    CLINIC = "clinic"
    HOTEL = "hotel"
    WORKSHOP = "workshop"
    OTHER = "other"


class BusinessCandidate(BaseModel):
    """A search hit, before any enrichment.

    Carries a single ``SourceRef`` because every field came from the same
    directory response in one call.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    external_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=200)
    category: BusinessCategory
    location: GeoPoint
    source: SourceRef
    address_line: str | None = Field(default=None, max_length=300)
    website: str | None = Field(default=None, max_length=2048)


def _iter_provenanced(model: BaseModel) -> Iterator[tuple[str, Provenanced[Any]]]:
    """Yield ``(field_path, provenanced_value)`` for every provenanced field.

    Walks one level into tuples so collection fields are covered too. Both the
    attribution renderer and the retention sweeper use this, so adding a new
    provenanced field keeps them correct without further edits.
    """
    for name, value in model:
        if isinstance(value, Provenanced):
            yield name, value
        elif isinstance(value, tuple):
            for index, item in enumerate(value):
                if isinstance(item, Provenanced):
                    yield f"{name}[{index}]", item


class BusinessProfile(BaseModel):
    """An enriched business, assembled from one or more permitted sources.

    Deliberately excludes reviews, ratings, and any named individual: none are
    needed to infer a design brief, and all carry heavier licensing and privacy
    obligations than the rest of the profile.
    """

    model_config = ConfigDict(extra="forbid")

    id: Slug
    name: Provenanced[str]
    category: Provenanced[BusinessCategory]
    location: Provenanced[GeoPoint]
    address_line: Provenanced[str] | None = None
    website: Provenanced[str] | None = None
    phone: Provenanced[str] | None = None
    descriptors: tuple[Provenanced[str], ...] = Field(
        default=(),
        max_length=MAX_DESCRIPTORS,
        description="Short public descriptors such as 'outdoor seating' or 'halal'.",
    )
    photo_urls: tuple[Provenanced[str], ...] = Field(default=(), max_length=MAX_PHOTOS)

    def attributions(self) -> tuple[str, ...]:
        """Distinct attribution strings that must be displayed with this profile.

        Insertion-ordered so rendered pages do not churn between builds.
        """
        seen: dict[str, None] = {}
        for _, provenanced in _iter_provenanced(self):
            text = provenanced.source.attribution
            if text is not None:
                seen.setdefault(text, None)
        return tuple(seen)

    def expired_fields(self, now: datetime) -> tuple[str, ...]:
        """Field paths whose retention window has closed.

        The retention sweeper purges these; a non-empty result on a profile
        about to be rendered is a bug, not a warning.
        """
        return tuple(
            path for path, provenanced in _iter_provenanced(self) if provenanced.is_expired(now)
        )

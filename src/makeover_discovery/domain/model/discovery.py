"""Discovery request and result models.

These are the use case's own vocabulary. They are not part of
``makeover-contracts`` because the render repo has no business knowing what a
postcode search looks like; only the HTTP and CLI interfaces of *this* service
speak them.
"""

from __future__ import annotations

from typing import Final

from makeover_contracts.business import BusinessCandidate, BusinessCategory
from makeover_contracts.geo import GeoArea, Postcode
from pydantic import BaseModel, ConfigDict, Field, field_validator

DEFAULT_RESULT_LIMIT: Final = 20
MAX_RESULT_LIMIT: Final = 50


class SearchFilters(BaseModel):
    """What to look for, independent of where.

    Separate from ``DiscoveryQuery`` because the ``BusinessDirectory`` port
    takes an area and these filters: a directory adapter must never see a
    postcode, or it would grow a dependency on how the area was derived.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    categories: tuple[BusinessCategory, ...] = Field(
        default=(),
        max_length=len(BusinessCategory),
        description="Empty means every category the provider can classify.",
    )
    limit: int = Field(default=DEFAULT_RESULT_LIMIT, ge=1, le=MAX_RESULT_LIMIT)

    @field_validator("categories")
    @classmethod
    def _drop_duplicates(cls, value: tuple[BusinessCategory, ...]) -> tuple[BusinessCategory, ...]:
        # Order is preserved so a repeated category cannot change the generated
        # provider query, which would otherwise defeat response caching.
        return tuple(dict.fromkeys(value))


class DiscoveryQuery(BaseModel):
    """One postcode lookup."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    postcode: Postcode
    filters: SearchFilters = SearchFilters()


class DiscoveryResult(BaseModel):
    """Businesses found for a postcode, with the attribution they oblige."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    postcode: Postcode
    area: GeoArea
    candidates: tuple[BusinessCandidate, ...]
    attributions: tuple[str, ...] = Field(
        default=(),
        description="Credit lines the caller must display alongside these results.",
    )

    @classmethod
    def build(
        cls,
        postcode: Postcode,
        area: GeoArea,
        candidates: tuple[BusinessCandidate, ...],
    ) -> DiscoveryResult:
        """Assemble a result, deriving attribution from the candidates' licences.

        Derived rather than passed in: an adapter that forgets to declare its
        credit line is a licence breach, and the only way to make that
        impossible is to never let a caller supply the value.
        """
        seen: dict[str, None] = {}
        for candidate in candidates:
            text = candidate.source.attribution
            if text is not None:
                seen.setdefault(text, None)
        return cls(postcode=postcode, area=area, candidates=candidates, attributions=tuple(seen))

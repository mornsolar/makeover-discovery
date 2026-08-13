"""Business discovery endpoint."""

from __future__ import annotations

from fastapi import APIRouter
from makeover_contracts.business import BusinessCategory
from makeover_contracts.geo import Postcode
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from makeover_discovery.domain.errors import ValidationError as DomainValidationError
from makeover_discovery.domain.model.discovery import (
    DEFAULT_RESULT_LIMIT,
    MAX_RESULT_LIMIT,
    DiscoveryQuery,
    DiscoveryResult,
    SearchFilters,
)
from makeover_discovery.interfaces.api.deps import DiscoverBusinessesDep

router = APIRouter(tags=["discovery"])


class DiscoverRequest(BaseModel):
    """Wire shape of a discovery request.

    Separate from ``DiscoveryQuery`` on purpose: the wire form takes a flat
    postcode and country because that is what a client has, while the domain
    insists on a validated ``Postcode`` value object. Translating between them
    is this layer's job.
    """

    model_config = ConfigDict(extra="forbid")

    postcode: str = Field(min_length=2, max_length=12, examples=["50450"])
    country: str = Field(min_length=2, max_length=2, examples=["MY"])
    limit: int = Field(default=DEFAULT_RESULT_LIMIT, ge=1, le=MAX_RESULT_LIMIT)
    categories: tuple[BusinessCategory, ...] = ()

    def to_query(self) -> DiscoveryQuery:
        """Build the domain query, restating invalid input as a domain error.

        Without this, a malformed postcode would surface as a pydantic error
        raised from inside the handler body and be served as a 500.
        """
        try:
            postcode = Postcode(value=self.postcode, country=self.country)
        except ValidationError as exc:
            raise DomainValidationError(str(exc)) from exc
        return DiscoveryQuery(
            postcode=postcode,
            filters=SearchFilters(categories=self.categories, limit=self.limit),
        )


@router.post(
    "/discover",
    response_model=DiscoveryResult,
    summary="Find businesses near a postcode",
)
async def discover(payload: DiscoverRequest, use_case: DiscoverBusinessesDep) -> DiscoveryResult:
    return await use_case.execute(payload.to_query())

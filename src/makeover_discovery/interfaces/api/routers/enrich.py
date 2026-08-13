"""Business enrichment endpoint."""

from __future__ import annotations

from fastapi import APIRouter
from makeover_contracts.business import BusinessCandidate, BusinessProfile
from pydantic import BaseModel, ConfigDict

from makeover_discovery.application.use_cases.enrich_business_profile import WebsiteOutcome
from makeover_discovery.interfaces.api.deps import EnrichBusinessProfileDep

router = APIRouter(tags=["discovery"])


class EnrichResponse(BaseModel):
    """An enriched profile plus what happened when we tried its website."""

    model_config = ConfigDict(extra="forbid")

    profile: BusinessProfile
    website_outcome: WebsiteOutcome
    attributions: tuple[str, ...]


@router.post(
    "/enrich",
    response_model=EnrichResponse,
    summary="Enrich a discovered business with permitted public information",
)
async def enrich(
    candidate: BusinessCandidate,
    use_case: EnrichBusinessProfileDep,
) -> EnrichResponse:
    result = await use_case.execute(candidate)
    return EnrichResponse(
        profile=result.profile,
        website_outcome=result.website_outcome,
        # Derived from the profile's own sources, so a caller cannot display it
        # without the credit its licences require.
        attributions=result.profile.attributions(),
    )

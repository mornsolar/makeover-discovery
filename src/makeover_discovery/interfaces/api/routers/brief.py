"""Design-brief endpoint."""

from __future__ import annotations

from fastapi import APIRouter
from makeover_contracts.brief import DesignBrief
from makeover_contracts.business import BusinessProfile
from pydantic import BaseModel, ConfigDict

from makeover_discovery.interfaces.api.deps import GenerateDesignBriefDep

router = APIRouter(tags=["brief"])


class BriefUsage(BaseModel):
    """What the brief cost, reported alongside it rather than only logged."""

    model_config = ConfigDict(extra="forbid")

    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int
    cache_write_input_tokens: int
    estimated_cost_usd: float


class BriefResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brief: DesignBrief
    usage: BriefUsage
    attempts: int
    repaired_problems: tuple[str, ...]
    attributions: tuple[str, ...]


@router.post(
    "/brief",
    response_model=BriefResponse,
    summary="Infer art direction for an enriched business profile",
)
async def brief(profile: BusinessProfile, use_case: GenerateDesignBriefDep) -> BriefResponse:
    result = await use_case.execute(profile)
    return BriefResponse(
        brief=result.brief,
        usage=BriefUsage(
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            cache_read_input_tokens=result.usage.cache_read_input_tokens,
            cache_write_input_tokens=result.usage.cache_write_input_tokens,
            estimated_cost_usd=result.cost_usd,
        ),
        attempts=result.attempts,
        repaired_problems=result.repaired_problems,
        # The brief is derived from the profile, so the profile's licences still
        # apply to anything rendered from it.
        attributions=profile.attributions(),
    )

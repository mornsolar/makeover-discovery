"""Infer art direction for one business, constrained to what the renderer can do."""

from __future__ import annotations

import hashlib

from makeover_contracts.brief import MAX_SEED, DesignBrief
from makeover_contracts.business import BusinessProfile

from makeover_discovery.application.ports.brief_generator import BriefGenerator
from makeover_discovery.application.ports.capability_source import CapabilitySource
from makeover_discovery.domain.errors import UpstreamError
from makeover_discovery.domain.model.brief import (
    MANDATORY_EXCLUSIONS,
    BriefRequest,
    BriefResult,
    BriefVocabulary,
)
from makeover_discovery.domain.model.llm import ModelPricing, TokenUsage
from makeover_discovery.domain.policy.brief_guardrails import validate_brief

MAX_DO_NOT_INCLUDE = 12
"""The contract's own ceiling on ``DesignBrief.do_not_include``."""


class GenerateDesignBrief:
    """Generates a brief, checks it, and repairs it once before giving up.

    One repair round rather than a loop: if a model cannot produce a valid brief
    when handed the exact list of what was wrong, further attempts mostly buy
    latency and tokens. Failing loudly is more useful than retrying quietly.

    The repair round also covers a generation call that raises ``UpstreamError``
    outright (e.g. a schema-valid tool call whose ``signage.tone`` still breaks
    the contract's length bound) - not just ``validate_brief``'s guardrail
    findings. Without this, that failure mode skipped the repair budget entirely
    and ended the attempt on the first bad response.
    """

    def __init__(
        self,
        generator: BriefGenerator,
        capabilities: CapabilitySource,
        pricing: ModelPricing,
        *,
        max_repair_attempts: int = 1,
    ) -> None:
        self._generator = generator
        self._capabilities = capabilities
        self._pricing = pricing
        self._max_repair_attempts = max_repair_attempts

    async def execute(self, profile: BusinessProfile) -> BriefResult:
        vocabulary = BriefVocabulary.from_manifest(await self._capabilities.manifest())
        seed = seed_for(profile)

        usage = TokenUsage()
        problems: tuple[str, ...] = ()
        for attempt in range(self._max_repair_attempts + 1):
            request = BriefRequest(
                profile=profile,
                vocabulary=vocabulary,
                seed=seed,
                problems=problems,
            )
            try:
                generated = await self._generator.generate(request)
            except UpstreamError as exc:
                problems = (str(exc),)
                continue
            usage += generated.usage

            brief = _with_mandatory_exclusions(generated.brief)
            remaining = validate_brief(brief, vocabulary)
            if not remaining:
                return BriefResult(
                    brief=brief,
                    usage=usage,
                    cost_usd=self._pricing.cost_usd(usage),
                    attempts=attempt + 1,
                    repaired_problems=problems,
                )
            problems = remaining

        # Surfaced, not silently downgraded: an unrenderable or non-compliant
        # brief must never reach a scene, so the caller learns why.
        raise UpstreamError(
            f"the model could not produce a usable brief for {profile.id} after "
            f"{self._max_repair_attempts + 1} attempt(s): {'; '.join(problems)}"
        )


def seed_for(profile: BusinessProfile) -> int:
    """A stable seed derived from the business identity.

    Deterministic on purpose: re-running the pipeline for the same business
    should reproduce the same art direction rather than churn the landing page.
    """
    digest = hashlib.sha256(profile.id.encode()).digest()
    return int.from_bytes(digest[:4], "big") % (MAX_SEED + 1)


def _with_mandatory_exclusions(brief: DesignBrief) -> DesignBrief:
    """Add the exclusions compliance requires, keeping whatever the model added.

    Written here rather than requested in the prompt so the guarantee holds even
    if the model ignores the instruction entirely.
    """
    merged = list(MANDATORY_EXCLUSIONS)
    merged.extend(item for item in brief.do_not_include if item not in merged)
    return brief.model_copy(update={"do_not_include": tuple(merged[:MAX_DO_NOT_INCLUDE])})

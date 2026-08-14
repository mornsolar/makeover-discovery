"""Builders and doubles for design-brief generation.

The deterministic generator here is what lets the whole pipeline be tested - and
the golden-brief eval run - without an API key, a network, or a bill.
"""

from __future__ import annotations

from makeover_contracts.brief import BriefGeneration, DesignBrief, LightingMood, SignageBrief
from makeover_contracts.business import BusinessCategory, BusinessProfile
from makeover_contracts.capability import CapabilityManifest
from makeover_contracts.geo import GeoPoint
from makeover_contracts.provenance import Provenanced

from makeover_discovery.domain.model.brief import (
    MANDATORY_EXCLUSIONS,
    BriefRequest,
    BriefVocabulary,
    GeneratedBrief,
)
from makeover_discovery.domain.model.llm import TokenUsage
from makeover_discovery.infrastructure.capabilities.static_manifest import BUILTIN_MANIFEST
from makeover_discovery.infrastructure.llm.prompts.brief_v1 import PROMPT_VERSION
from tests.fakes.candidates import FETCHED_AT, osm_source

VOCABULARY = BriefVocabulary.from_manifest(BUILTIN_MANIFEST)

PALETTE_BY_CATEGORY = {
    BusinessCategory.CAFE: ("#1B4D3E", "#E8DCC4", "#C87941"),
    BusinessCategory.BAKERY: ("#F4E4C1", "#8B5E3C", "#FFFFFF"),
    BusinessCategory.SALON: ("#2E2A38", "#D9C7B8", "#B08D57"),
}
DEFAULT_PALETTE = ("#2B2B2B", "#E5E5E5", "#8A9A5B")

DEFAULT_USAGE = TokenUsage(input_tokens=1_000, output_tokens=200)

DEFAULT_RATIONALE = (
    "The category reads as an everyday neighbourhood stop, so the direction "
    "stays warm and unfussy rather than boutique."
)


def make_profile(
    *,
    business_id: str = "kedai-kopi-ali-node-1",
    name: str = "Kedai Kopi Ali",
    category: BusinessCategory = BusinessCategory.CAFE,
    descriptors: tuple[str, ...] = ("halal", "outdoor seating"),
    photo_urls: tuple[str, ...] = (),
) -> BusinessProfile:
    source = osm_source()
    return BusinessProfile(
        id=business_id,
        name=Provenanced(value=name, source=source),
        category=Provenanced(value=category, source=source),
        location=Provenanced(value=GeoPoint(lat=3.16, lon=101.71), source=source),
        descriptors=tuple(Provenanced(value=text, source=source) for text in descriptors),
        photo_urls=tuple(Provenanced(value=url, source=source) for url in photo_urls),
    )


def make_brief(
    profile: BusinessProfile | None = None,
    *,
    vocabulary: BriefVocabulary = VOCABULARY,
    material_families: tuple[str, ...] | None = None,
    camera_move: str | None = None,
    lighting_mood: LightingMood | None = None,
    signage_text: str | None = None,
    rationale: str = DEFAULT_RATIONALE,
    do_not_include: tuple[str, ...] = MANDATORY_EXCLUSIONS,
    seed: int = 7,
) -> DesignBrief:
    profile = profile or make_profile()
    return DesignBrief(
        business_id=profile.id,
        style_direction=(
            "Warm mid-century kopitiam frontage with a deep timber fascia and a "
            "single hand-lettered sign."
        ),
        palette=PALETTE_BY_CATEGORY.get(profile.category.value, DEFAULT_PALETTE),
        material_families=material_families or vocabulary.material_families[:2],
        signage=SignageBrief(
            text=signage_text or profile.name.value[:40],
            tone="hand-painted, unhurried",
        ),
        lighting_mood=lighting_mood or vocabulary.lighting_moods[0],
        camera_move=camera_move or vocabulary.camera_moves[0],
        rationale=rationale,
        do_not_include=do_not_include,
        generation=BriefGeneration(
            model="fake-model",
            prompt_version=PROMPT_VERSION,
            seed=seed,
            generated_at=FETCHED_AT,
        ),
    )


class FakeBriefGenerator:
    """Returns a valid brief, recording every request it was given."""

    def __init__(
        self,
        briefs: list[DesignBrief] | None = None,
        usage: TokenUsage = DEFAULT_USAGE,
    ) -> None:
        self._briefs = briefs
        self._usage = usage
        self.requests: list[BriefRequest] = []

    async def generate(self, request: BriefRequest) -> GeneratedBrief:
        self.requests.append(request)
        if self._briefs is None:
            brief = make_brief(request.profile, vocabulary=request.vocabulary, seed=request.seed)
        else:
            # Scripted briefs drive the repair round: first invalid, then valid.
            index = min(len(self.requests) - 1, len(self._briefs) - 1)
            brief = self._briefs[index]
        return GeneratedBrief(brief=brief, usage=self._usage)


class FakeCapabilitySource:
    """Serves a fixed manifest without touching the render service."""

    def __init__(self, manifest: CapabilityManifest = BUILTIN_MANIFEST) -> None:
        self._manifest = manifest

    async def manifest(self) -> CapabilityManifest:
        return self._manifest

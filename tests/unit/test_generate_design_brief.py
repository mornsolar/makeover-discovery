"""The design-brief use case."""

from __future__ import annotations

import pytest

from makeover_discovery.application.use_cases.generate_design_brief import (
    GenerateDesignBrief,
    seed_for,
)
from makeover_discovery.domain.errors import UpstreamError
from makeover_discovery.domain.model.brief import MANDATORY_EXCLUSIONS
from makeover_discovery.domain.model.llm import TokenUsage
from makeover_discovery.infrastructure.llm.pricing import DEFAULT_MODEL, pricing_for
from tests.fakes.brief import (
    FakeBriefGenerator,
    FakeCapabilitySource,
    make_brief,
    make_profile,
)

PRICING = pricing_for(DEFAULT_MODEL)
PROFILE = make_profile()


def build(generator: FakeBriefGenerator, *, max_repair_attempts: int = 1) -> GenerateDesignBrief:
    return GenerateDesignBrief(
        generator=generator,
        capabilities=FakeCapabilitySource(),
        pricing=PRICING,
        max_repair_attempts=max_repair_attempts,
    )


async def test_returns_a_brief_for_the_profile():
    result = await build(FakeBriefGenerator()).execute(PROFILE)

    assert result.brief.business_id == PROFILE.id
    assert result.attempts == 1


async def test_constrains_the_generator_to_the_renderer_vocabulary():
    generator = FakeBriefGenerator()

    await build(generator).execute(PROFILE)

    assert "timber" in generator.requests[0].vocabulary.material_families


async def test_seeds_the_request_from_the_business_identity():
    # Re-running the pipeline for the same business must not churn its page.
    generator = FakeBriefGenerator()

    await build(generator).execute(PROFILE)

    assert generator.requests[0].seed == seed_for(PROFILE)


async def test_the_seed_is_stable_across_runs():
    assert seed_for(PROFILE) == seed_for(make_profile())


async def test_different_businesses_get_different_seeds():
    assert seed_for(PROFILE) != seed_for(make_profile(business_id="roti-bakar-2"))


async def test_adds_the_mandatory_exclusions_the_model_omitted():
    # Compliance cannot depend on the model remembering an instruction.
    generator = FakeBriefGenerator([make_brief(do_not_include=("neon",))])

    result = await build(generator).execute(PROFILE)

    assert set(MANDATORY_EXCLUSIONS) <= set(result.brief.do_not_include)


async def test_keeps_the_exclusions_the_model_added():
    generator = FakeBriefGenerator([make_brief(do_not_include=("neon",))])

    result = await build(generator).execute(PROFILE)

    assert "neon" in result.brief.do_not_include


async def test_repairs_a_brief_that_leaves_the_vocabulary():
    invalid = make_brief(material_families=("unobtainium",))
    generator = FakeBriefGenerator([invalid, make_brief()])

    result = await build(generator).execute(PROFILE)

    assert result.attempts == 2
    assert result.brief.material_families != ("unobtainium",)


async def test_tells_the_generator_exactly_what_was_wrong():
    generator = FakeBriefGenerator([make_brief(camera_move="barrel_roll"), make_brief()])

    await build(generator).execute(PROFILE)

    assert any("barrel_roll" in problem for problem in generator.requests[1].problems)


async def test_records_which_problems_a_repair_fixed():
    generator = FakeBriefGenerator([make_brief(camera_move="barrel_roll"), make_brief()])

    result = await build(generator).execute(PROFILE)

    assert result.repaired_problems != ()


async def test_bills_every_attempt_including_the_failed_one():
    usage = TokenUsage(input_tokens=1_000, output_tokens=200)
    generator = FakeBriefGenerator([make_brief(camera_move="barrel_roll"), make_brief()], usage)

    result = await build(generator).execute(PROFILE)

    assert result.usage == usage + usage
    assert result.cost_usd == pytest.approx(PRICING.cost_usd(usage + usage))


async def test_fails_loudly_when_the_model_cannot_be_repaired():
    # An unrenderable brief must never reach a scene, so this surfaces rather
    # than returning something the renderer would silently reject later.
    generator = FakeBriefGenerator([make_brief(camera_move="barrel_roll")])

    with pytest.raises(UpstreamError, match="barrel_roll"):
        await build(generator).execute(PROFILE)


async def test_makes_no_repair_attempt_when_repairs_are_disabled():
    generator = FakeBriefGenerator([make_brief(camera_move="barrel_roll")])

    with pytest.raises(UpstreamError):
        await build(generator, max_repair_attempts=0).execute(PROFILE)

    assert len(generator.requests) == 1


async def test_repairs_a_generation_call_that_raises_outright():
    # A schema-valid tool call can still fail DesignBrief's own contract
    # validation (e.g. signage.tone over 80 characters) - that raises
    # UpstreamError from generate() itself, before validate_brief ever runs.
    generator = FakeBriefGenerator([UpstreamError("signage.tone: string too long"), make_brief()])

    result = await build(generator).execute(PROFILE)

    assert result.attempts == 2


async def test_tells_the_generator_what_the_generation_failure_was():
    generator = FakeBriefGenerator([UpstreamError("signage.tone: string too long"), make_brief()])

    await build(generator).execute(PROFILE)

    assert any("too long" in problem for problem in generator.requests[1].problems)


async def test_fails_loudly_when_generation_keeps_failing():
    generator = FakeBriefGenerator([UpstreamError("signage.tone: string too long")])

    with pytest.raises(UpstreamError, match="too long"):
        await build(generator).execute(PROFILE)

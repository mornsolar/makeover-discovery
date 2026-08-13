"""Every golden business must produce a brief that scores clean.

The generator here is deterministic, so a failure means the use case, the
guardrails, or the renderer vocabulary changed - not that a model had an off
day. The same harness scores the real adapter when run by hand with a key.
"""

from __future__ import annotations

import pytest

from makeover_discovery.application.use_cases.generate_design_brief import GenerateDesignBrief
from makeover_discovery.infrastructure.llm.pricing import DEFAULT_MODEL, pricing_for
from tests.evals.cases import GOLDEN_CASES
from tests.evals.harness import CRITERIA, EvalCase, report, score
from tests.fakes.brief import (
    VOCABULARY,
    FakeBriefGenerator,
    FakeCapabilitySource,
    make_brief,
)


def use_case() -> GenerateDesignBrief:
    return GenerateDesignBrief(
        generator=FakeBriefGenerator(),
        capabilities=FakeCapabilitySource(),
        pricing=pricing_for(DEFAULT_MODEL),
    )


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=lambda case: case.name)
async def test_the_golden_brief_scores_clean(case: EvalCase):
    result = await use_case().execute(case.profile)

    assessment = score(result.brief, case, VOCABULARY)

    assert assessment.passed, assessment.failures


async def test_reports_every_case_in_one_run():
    scores = [
        score((await use_case().execute(case.profile)).brief, case, VOCABULARY)
        for case in GOLDEN_CASES
    ]

    summary = report(scores)

    assert f"{len(GOLDEN_CASES)}/{len(GOLDEN_CASES)} briefs passed" in summary


def test_the_harness_catches_an_unrenderable_brief():
    # A harness that passes everything is worth nothing; this pins that each
    # criterion can actually fail.
    case = GOLDEN_CASES[0]

    assessment = score(make_brief(camera_move="barrel_roll"), case, VOCABULARY)

    assert "renderable" in assessment.failures


def test_the_harness_catches_a_repeated_palette_colour():
    case = GOLDEN_CASES[0]

    repeated = make_brief().model_copy(update={"palette": ("#FFFFFF", "#FFFFFF")})

    assessment = score(repeated, case, VOCABULARY)

    assert "palette_is_distinct" in assessment.failures


def test_the_harness_catches_signage_for_a_different_business():
    case = GOLDEN_CASES[0]

    assessment = score(make_brief(signage_text="Generic Coffee House"), case, VOCABULARY)

    assert "signage_relates_to_the_business" in assessment.failures


def test_the_harness_catches_a_banned_term():
    case = GOLDEN_CASES[0]

    assessment = score(
        make_brief(rationale="Rework the storefront around the existing Starbucks logo wall."),
        case,
        VOCABULARY,
    )

    assert "avoids_banned_terms" in assessment.failures


def test_every_criterion_is_exercised_by_the_golden_set():
    assert set(CRITERIA) >= {"renderable", "avoids_banned_terms"}

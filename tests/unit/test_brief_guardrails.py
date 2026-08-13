"""The checks a brief must pass before it can be rendered or published."""

from __future__ import annotations

from makeover_contracts.brief import LightingMood

from makeover_discovery.domain.model.brief import MANDATORY_EXCLUSIONS, BriefVocabulary
from makeover_discovery.domain.policy.brief_guardrails import validate_brief
from tests.fakes.brief import VOCABULARY, make_brief


def problems(**changes) -> tuple[str, ...]:
    return validate_brief(make_brief().model_copy(update=changes), VOCABULARY)


def test_accepts_a_brief_inside_the_vocabulary():
    assert validate_brief(make_brief(), VOCABULARY) == ()


def test_rejects_a_material_the_renderer_does_not_ship():
    found = problems(material_families=("timber", "unobtainium"))

    assert any("unobtainium" in problem for problem in found)


def test_lists_what_the_renderer_does_offer():
    # The message is fed straight back to the model as repair instructions, so
    # naming the alternatives is the difference between one round and none.
    found = problems(camera_move="barrel_roll")

    assert any("orbit" in problem for problem in found)


def test_rejects_a_mood_with_no_matching_lighting_rig():
    narrow = BriefVocabulary(
        material_families=VOCABULARY.material_families,
        camera_moves=VOCABULARY.camera_moves,
        lighting_moods=(LightingMood.BRIGHT_DAYLIGHT,),
    )

    found = validate_brief(make_brief(lighting_mood=LightingMood.NEON_NIGHT), narrow)

    assert any("neon_night" in problem for problem in found)


def test_reports_every_problem_at_once():
    found = problems(material_families=("unobtainium",), camera_move="barrel_roll")

    assert len(found) == 2


def test_rejects_trademark_marks_in_signage():
    found = problems(signage=make_brief().signage.model_copy(update={"text": "Kopi Ali®"}))

    assert any("trademark" in problem for problem in found)


def test_rejects_an_unsourced_founding_year():
    # Every other field in the system is provenanced; a generated brief has no
    # source at all, so it must assert nothing checkable.
    found = problems(rationale="A kopitiam serving the same street since 1968, so the " * 2)

    assert any("since 1968" in problem for problem in found)


def test_rejects_an_invented_accolade():
    found = problems(rationale="The award-winning kopitiam deserves a frontage to match it.")

    assert any("unsourced factual claim" in problem for problem in found)


def test_rejects_an_invented_rating():
    found = problems(rationale="A 4.8 stars neighbourhood favourite, styled to suit it.")

    assert any("unsourced factual claim" in problem for problem in found)


def test_requires_the_mandatory_exclusions():
    found = problems(do_not_include=("neon",))

    assert any("mandatory entries" in problem for problem in found)


def test_accepts_extra_exclusions_alongside_the_mandatory_ones():
    assert problems(do_not_include=(*MANDATORY_EXCLUSIONS, "neon")) == ()

"""``ComposeSceneSpec``, against the compiled-in manifest."""

from __future__ import annotations

import pytest
from makeover_contracts.capability import validate_against_manifest

from makeover_discovery.application.use_cases.compose_scene_spec import ComposeSceneSpec
from makeover_discovery.domain.errors import UpstreamError
from makeover_discovery.infrastructure.capabilities.static_manifest import BUILTIN_MANIFEST
from tests.fakes.brief import make_brief, make_profile

COMPOSE = ComposeSceneSpec()


def test_produces_a_spec_that_passes_manifest_validation():
    profile = make_profile()
    brief = make_brief(profile)

    spec = COMPOSE.execute(profile, brief, BUILTIN_MANIFEST)

    assert validate_against_manifest(spec, BUILTIN_MANIFEST) == ()


def test_material_slots_match_the_chosen_template_exactly():
    profile = make_profile()
    brief = make_brief(profile)

    spec = COMPOSE.execute(profile, brief, BUILTIN_MANIFEST)

    template = BUILTIN_MANIFEST.template(spec.template_id)
    assert template is not None
    assert {a.slot for a in spec.materials} == set(template.material_slots)


def test_the_chosen_template_is_stable_across_two_calls():
    # Re-running the pipeline for the same business must reproduce the same
    # scene, not churn the landing page on every run.
    profile = make_profile(business_id="stable-business-1")
    brief = make_brief(profile)

    first = COMPOSE.execute(profile, brief, BUILTIN_MANIFEST)
    second = COMPOSE.execute(profile, brief, BUILTIN_MANIFEST)

    assert first.template_id == second.template_id


def test_reuses_the_briefs_seed_rather_than_deriving_a_new_one():
    profile = make_profile()
    brief = make_brief(profile, seed=42)

    spec = COMPOSE.execute(profile, brief, BUILTIN_MANIFEST)

    assert spec.seed == 42


def test_truncates_a_business_name_too_long_for_signage():
    # The renderer's signage caps at 40 chars; nothing about a business's own
    # name is bound by that, so this repo must truncate before composing.
    long_name = "A" * 60
    profile = make_profile(name=long_name)
    brief = make_brief(profile)

    spec = COMPOSE.execute(profile, brief, BUILTIN_MANIFEST)

    assert len(spec.signage.text) <= 40
    assert spec.signage.text.startswith("A" * 10)


def test_a_business_name_within_the_limit_is_not_truncated():
    profile = make_profile(name="Kedai Kopi Ali")
    brief = make_brief(profile)

    spec = COMPOSE.execute(profile, brief, BUILTIN_MANIFEST)

    assert spec.signage.text == "Kedai Kopi Ali"


def test_maps_lighting_mood_onto_the_matching_preset():
    profile = make_profile()
    brief = make_brief(profile)

    spec = COMPOSE.execute(profile, brief, BUILTIN_MANIFEST)

    # LightingMood and LightingPreset are separate enum classes that share the
    # same string values by design; this is the one-to-one mapping working.
    assert spec.lighting.preset.value == brief.lighting_mood.value


def test_raises_when_the_manifest_used_to_compose_disagrees_with_the_brief():
    # Simulates the two repos' capability manifests drifting apart: a brief
    # built against one vocabulary, composed against a manifest that no
    # longer offers the material family it used.
    profile = make_profile()
    brief = make_brief(profile, material_families=("timber",))
    drifted = BUILTIN_MANIFEST.model_copy(update={"material_families": ("steel",)})

    with pytest.raises(UpstreamError, match="not renderable"):
        COMPOSE.execute(profile, brief, drifted)

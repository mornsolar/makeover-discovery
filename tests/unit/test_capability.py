from __future__ import annotations

from makeover_contracts.capability import (
    CapabilityManifest,
    RenderLimits,
    TemplateDescriptor,
    validate_against_manifest,
)
from makeover_contracts.scene import (
    CameraMove,
    CameraSpec,
    LightingPreset,
    LightingSpec,
    MaterialAssignment,
    MaterialSlot,
    RenderEngine,
    RenderSpec,
    SceneSpec,
    SignageSpec,
    StorefrontDimensions,
)

MANIFEST = CapabilityManifest(
    renderer_name="makeover-render",
    engine_version="5.2.0 LTS",
    templates=(
        TemplateDescriptor(
            id="shophouse-narrow",
            label="Narrow shophouse",
            description="Two-storey shophouse frontage with an awning.",
            material_slots=(MaterialSlot.FACADE, MaterialSlot.SIGN, MaterialSlot.AWNING),
        ),
    ),
    material_families=("timber", "brass", "render"),
    lighting_presets=(LightingPreset.WARM_EVENING,),
    camera_moves=(CameraMove.ORBIT,),
    engines=(RenderEngine.EEVEE,),
    limits=RenderLimits(
        max_duration_s=10.0,
        max_fps=30,
        max_frame_count=300,
        max_resolution_x=1920,
        max_resolution_y=1080,
        max_samples=256,
    ),
)


def make_scene(**overrides) -> SceneSpec:
    defaults = {
        "template_id": "shophouse-narrow",
        "seed": 1,
        "dimensions": StorefrontDimensions(width_m=8.0, height_m=4.5, depth_m=6.0),
        "palette": ("#1B4D3E",),
        "materials": (
            MaterialAssignment(slot=MaterialSlot.FACADE, family="timber", base_color="#1B4D3E"),
        ),
        "signage": SignageSpec(text="KEDAI KOPI"),
        "lighting": LightingSpec(preset=LightingPreset.WARM_EVENING),
        "camera": CameraSpec(move=CameraMove.ORBIT, duration_s=5.0, fps=24),
    }
    return SceneSpec(**{**defaults, **overrides})


class TestManifestLookup:
    def test_finds_a_known_template(self):
        assert MANIFEST.template("shophouse-narrow") is not None

    def test_returns_none_for_an_unknown_template(self):
        assert MANIFEST.template("cathedral") is None


class TestValidateAgainstManifest:
    def test_accepts_a_spec_within_every_limit(self):
        assert validate_against_manifest(make_scene(), MANIFEST) == ()

    def test_reports_an_unknown_template_and_lists_the_alternatives(self):
        problems = validate_against_manifest(make_scene(template_id="cathedral"), MANIFEST)
        assert any("unknown template" in p and "shophouse-narrow" in p for p in problems)

    def test_reports_a_material_slot_the_template_lacks(self):
        scene = make_scene(
            materials=(
                MaterialAssignment(
                    slot=MaterialSlot.GLAZING, family="timber", base_color="#1B4D3E"
                ),
            )
        )
        problems = validate_against_manifest(scene, MANIFEST)
        assert any("no material slots" in p and "glazing" in p for p in problems)

    def test_reports_an_unknown_material_family(self):
        scene = make_scene(
            materials=(
                MaterialAssignment(
                    slot=MaterialSlot.FACADE, family="unobtanium", base_color="#1B4D3E"
                ),
            )
        )
        problems = validate_against_manifest(scene, MANIFEST)
        assert any("unknown material families: unobtanium" in p for p in problems)

    def test_reports_an_unsupported_engine(self):
        scene = make_scene(render=RenderSpec(engine=RenderEngine.CYCLES))
        problems = validate_against_manifest(scene, MANIFEST)
        assert any("unsupported render engine" in p for p in problems)

    def test_reports_a_duration_beyond_the_limit(self):
        scene = make_scene(camera=CameraSpec(move=CameraMove.ORBIT, duration_s=12.0, fps=24))
        problems = validate_against_manifest(scene, MANIFEST)
        assert any("exceeds" in p for p in problems)

    def test_reports_a_resolution_beyond_the_limit(self):
        scene = make_scene(render=RenderSpec(resolution_x=3840, resolution_y=2160))
        problems = validate_against_manifest(scene, MANIFEST)
        assert any("resolution_x" in p for p in problems)
        assert any("resolution_y" in p for p in problems)

    def test_reports_every_problem_in_one_pass(self):
        # One repair round should see all the failures, not just the first.
        scene = make_scene(
            template_id="cathedral",
            render=RenderSpec(engine=RenderEngine.CYCLES, samples=4096),
        )
        assert len(validate_against_manifest(scene, MANIFEST)) >= 3

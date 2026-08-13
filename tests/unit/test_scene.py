from __future__ import annotations

import pytest
from makeover_contracts.scene import (
    CameraMove,
    CameraSpec,
    LightingPreset,
    LightingSpec,
    MaterialAssignment,
    MaterialSlot,
    RenderSpec,
    SceneSpec,
    SignageSpec,
    StorefrontDimensions,
)
from pydantic import ValidationError

DIMENSIONS = StorefrontDimensions(width_m=8.0, height_m=4.5, depth_m=6.0)


def make_scene(**overrides) -> SceneSpec:
    defaults = {
        "template_id": "shophouse-narrow",
        "seed": 42,
        "dimensions": DIMENSIONS,
        "palette": ("#1B4D3E", "#E8D6B3"),
        "materials": (
            MaterialAssignment(slot=MaterialSlot.FACADE, family="timber", base_color="#1B4D3E"),
        ),
        "signage": SignageSpec(text="KEDAI KOPI"),
        "lighting": LightingSpec(preset=LightingPreset.WARM_EVENING),
        "camera": CameraSpec(move=CameraMove.ORBIT),
    }
    return SceneSpec(**{**defaults, **overrides})


class TestCameraSpec:
    def test_derives_frame_count_from_duration_and_fps(self):
        assert CameraSpec(move=CameraMove.ORBIT, duration_s=5.0, fps=24).frame_count == 120

    def test_rounds_fractional_frame_counts(self):
        assert CameraSpec(move=CameraMove.PAN, duration_s=2.5, fps=25).frame_count == 63

    def test_never_yields_fewer_than_one_frame(self):
        assert CameraSpec(move=CameraMove.PAN, duration_s=1.0, fps=12).frame_count == 12

    def test_rejects_a_duration_beyond_the_cap(self):
        with pytest.raises(ValidationError):
            CameraSpec(move=CameraMove.ORBIT, duration_s=16.0)


class TestSceneSpec:
    def test_rejects_two_assignments_to_one_material_slot(self):
        # Duplicate slots make the result depend on iteration order, which would
        # silently break render determinism.
        with pytest.raises(ValidationError, match="at most once"):
            make_scene(
                materials=(
                    MaterialAssignment(
                        slot=MaterialSlot.FACADE, family="timber", base_color="#1B4D3E"
                    ),
                    MaterialAssignment(
                        slot=MaterialSlot.FACADE, family="brass", base_color="#E8D6B3"
                    ),
                )
            )

    def test_accepts_distinct_material_slots(self):
        scene = make_scene(
            materials=(
                MaterialAssignment(slot=MaterialSlot.FACADE, family="timber", base_color="#1B4D3E"),
                MaterialAssignment(slot=MaterialSlot.SIGN, family="brass", base_color="#E8D6B3"),
            )
        )
        assert len(scene.materials) == 2

    def test_exposes_frame_count_from_its_camera(self):
        assert make_scene().frame_count == 120

    def test_defaults_to_eevee_at_720p(self):
        assert make_scene().render == RenderSpec()
        assert make_scene().render.resolution_y == 720

    def test_rejects_roughness_outside_the_unit_interval(self):
        with pytest.raises(ValidationError):
            MaterialAssignment(
                slot=MaterialSlot.TRIM, family="timber", base_color="#1B4D3E", roughness=1.5
            )

    def test_rejects_a_seed_outside_the_reproducible_range(self):
        with pytest.raises(ValidationError):
            make_scene(seed=-1)

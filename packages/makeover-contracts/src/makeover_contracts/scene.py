"""The renderer-facing scene description.

``SceneSpec`` is deliberately domain-free: it mentions storefronts, materials,
and cameras, never businesses or postcodes. That is what lets the render repo
stay reusable for any caller able to produce one.
"""

from __future__ import annotations

import math
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from makeover_contracts.primitives import HexColor, Slug, UnitInterval
from makeover_contracts.version import CONTRACT_VERSION

MAX_SEED = 2**31 - 1


class RenderEngine(StrEnum):
    """Values are Blender's own engine identifiers, assigned verbatim to
    ``scene.render.engine``."""

    EEVEE = "BLENDER_EEVEE"
    CYCLES = "CYCLES"


class CameraMove(StrEnum):
    ORBIT = "orbit"
    DOLLY_IN = "dolly_in"
    CRANE_DOWN = "crane_down"
    PAN = "pan"


class LightingPreset(StrEnum):
    """Concrete rigs. Mirrors ``LightingMood`` one-for-one today, but they stay
    separate types because mood is intent and preset is implementation."""

    WARM_EVENING = "warm_evening"
    BRIGHT_DAYLIGHT = "bright_daylight"
    NEON_NIGHT = "neon_night"
    SOFT_OVERCAST = "soft_overcast"


class MaterialSlot(StrEnum):
    """Named surfaces every storefront template exposes."""

    FACADE = "facade"
    TRIM = "trim"
    SIGN = "sign"
    GLAZING = "glazing"
    AWNING = "awning"
    GROUND = "ground"


class StorefrontDimensions(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    width_m: float = Field(gt=1.0, le=40.0)
    height_m: float = Field(gt=1.0, le=20.0)
    depth_m: float = Field(gt=0.5, le=20.0)


class MaterialAssignment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    slot: MaterialSlot
    family: str = Field(min_length=1, max_length=64)
    base_color: HexColor
    roughness: UnitInterval = 0.5
    metallic: UnitInterval = 0.0


class SignageSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str = Field(min_length=1, max_length=40)
    font_family: str = Field(default="Inter", max_length=64)
    emissive_strength: float = Field(default=0.0, ge=0.0, le=50.0)


class LightingSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    preset: LightingPreset
    key_energy_w: float = Field(default=200.0, gt=0.0, le=10_000.0)
    color_temperature_k: int = Field(default=5500, ge=1500, le=12_000)


class CameraSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    move: CameraMove
    duration_s: float = Field(default=5.0, ge=1.0, le=15.0)
    fps: int = Field(default=24, ge=12, le=60)
    focal_length_mm: float = Field(default=35.0, ge=10.0, le=200.0)

    @property
    def frame_count(self) -> int:
        """Frames to render, inclusive of the first.

        Derived rather than stored so duration and fps cannot disagree.

        Rounds half up explicitly. The builtin ``round`` is banker's rounding,
        which would turn 2.5s at 25fps into 62 frames rather than 63 — a
        surprise that would show up as an off-by-one in golden render tests.
        """
        return max(1, math.floor(self.duration_s * self.fps + 0.5))


class RenderSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    engine: RenderEngine = RenderEngine.EEVEE
    samples: int = Field(default=64, ge=1, le=4096)
    resolution_x: int = Field(default=1280, ge=16, le=3840)
    resolution_y: int = Field(default=720, ge=16, le=2160)
    film_transparent: bool = False


class SceneSpec(BaseModel):
    """A complete, deterministic description of one render job's input."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_version: str = CONTRACT_VERSION
    template_id: Slug
    seed: int = Field(ge=0, le=MAX_SEED)
    dimensions: StorefrontDimensions
    palette: tuple[HexColor, ...] = Field(min_length=1, max_length=6)
    materials: tuple[MaterialAssignment, ...] = Field(min_length=1)
    signage: SignageSpec
    lighting: LightingSpec
    camera: CameraSpec
    render: RenderSpec = RenderSpec()

    @model_validator(mode="after")
    def _reject_duplicate_slots(self) -> SceneSpec:
        # Two assignments to one slot makes the result depend on iteration
        # order, which would quietly break render determinism.
        slots = [assignment.slot for assignment in self.materials]
        if len(slots) != len(set(slots)):
            raise ValueError("each material slot may be assigned at most once")
        return self

    @property
    def frame_count(self) -> int:
        return self.camera.frame_count

"""What the renderer can actually do, and whether a spec fits inside it.

This module is how the two repositories avoid a circular dependency. The render
repo publishes a ``CapabilityManifest``; the discovery repo reads it, constrains
the LLM to that vocabulary, and validates the composed ``SceneSpec`` before
submitting. Both sides call :func:`validate_against_manifest`, so "would this
render?" has exactly one implementation.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from makeover_contracts.primitives import Slug
from makeover_contracts.scene import (
    CameraMove,
    LightingPreset,
    MaterialSlot,
    RenderEngine,
    SceneSpec,
)
from makeover_contracts.version import CONTRACT_VERSION


class RenderLimits(BaseModel):
    """Hard ceilings the renderer enforces, advertised so callers can pre-check."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_duration_s: float = Field(gt=0.0, le=60.0)
    max_fps: int = Field(ge=1, le=120)
    max_frame_count: int = Field(ge=1, le=7200)
    max_resolution_x: int = Field(ge=16, le=7680)
    max_resolution_y: int = Field(ge=16, le=4320)
    max_samples: int = Field(ge=1, le=16_384)


class TemplateDescriptor(BaseModel):
    """One storefront template the renderer ships."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Slug
    label: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=400)
    material_slots: tuple[MaterialSlot, ...] = Field(min_length=1)


class CapabilityManifest(BaseModel):
    """The renderer's self-description."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_version: str = CONTRACT_VERSION
    renderer_name: str = Field(min_length=1, max_length=64)
    engine_version: str = Field(min_length=1, max_length=64)
    templates: tuple[TemplateDescriptor, ...] = Field(min_length=1)
    material_families: tuple[str, ...] = Field(min_length=1)
    lighting_presets: tuple[LightingPreset, ...] = Field(min_length=1)
    camera_moves: tuple[CameraMove, ...] = Field(min_length=1)
    engines: tuple[RenderEngine, ...] = Field(min_length=1)
    limits: RenderLimits

    def template(self, template_id: str) -> TemplateDescriptor | None:
        return next((t for t in self.templates if t.id == template_id), None)


def validate_against_manifest(spec: SceneSpec, manifest: CapabilityManifest) -> tuple[str, ...]:
    """Return human-readable reasons ``spec`` cannot be rendered by ``manifest``.

    An empty tuple means the spec is renderable. Returning reasons rather than
    raising lets the discovery repo feed every problem back to the LLM in one
    repair round instead of one problem per attempt.
    """
    problems: list[str] = []

    template = manifest.template(spec.template_id)
    if template is None:
        known = ", ".join(sorted(t.id for t in manifest.templates))
        problems.append(f"unknown template {spec.template_id!r}; renderer offers: {known}")
    else:
        unsupported = {a.slot for a in spec.materials} - set(template.material_slots)
        if unsupported:
            names = ", ".join(sorted(slot.value for slot in unsupported))
            problems.append(f"template {template.id!r} has no material slots: {names}")

    unknown_families = {
        a.family for a in spec.materials if a.family not in manifest.material_families
    }
    if unknown_families:
        problems.append(f"unknown material families: {', '.join(sorted(unknown_families))}")

    if spec.lighting.preset not in manifest.lighting_presets:
        problems.append(f"unsupported lighting preset {spec.lighting.preset.value!r}")
    if spec.camera.move not in manifest.camera_moves:
        problems.append(f"unsupported camera move {spec.camera.move.value!r}")
    if spec.render.engine not in manifest.engines:
        problems.append(f"unsupported render engine {spec.render.engine.value!r}")

    limits = manifest.limits
    if spec.camera.duration_s > limits.max_duration_s:
        problems.append(f"duration {spec.camera.duration_s}s exceeds {limits.max_duration_s}s")
    if spec.camera.fps > limits.max_fps:
        problems.append(f"fps {spec.camera.fps} exceeds {limits.max_fps}")
    if spec.frame_count > limits.max_frame_count:
        problems.append(f"frame count {spec.frame_count} exceeds {limits.max_frame_count}")
    if spec.render.resolution_x > limits.max_resolution_x:
        problems.append(
            f"resolution_x {spec.render.resolution_x} exceeds {limits.max_resolution_x}"
        )
    if spec.render.resolution_y > limits.max_resolution_y:
        problems.append(
            f"resolution_y {spec.render.resolution_y} exceeds {limits.max_resolution_y}"
        )
    if spec.render.samples > limits.max_samples:
        problems.append(f"samples {spec.render.samples} exceeds {limits.max_samples}")

    return tuple(problems)

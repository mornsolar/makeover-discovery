"""Turn a ``DesignBrief`` into a ``SceneSpec`` the renderer can build.

The one place in this phase with real judgment calls: no business data this
repo gathers today describes a storefront's actual footprint or which of the
renderer's templates would suit it best, so every choice below is a
deliberately simple, deterministic heuristic - not aesthetic optimisation.
Re-running the pipeline for the same business must reproduce the same scene,
so nothing here uses randomness beyond what the business's own identity
already determines.
"""

from __future__ import annotations

import hashlib
from typing import Final

from makeover_contracts.brief import DesignBrief
from makeover_contracts.business import BusinessProfile
from makeover_contracts.capability import (
    CapabilityManifest,
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

from makeover_discovery.domain.errors import UpstreamError

DEFAULT_DIMENSIONS: Final = StorefrontDimensions(width_m=6.0, height_m=3.2, depth_m=4.0)
"""No source of real footprint data exists yet; every composed scene uses this
until a future phase gathers it."""

MAX_SIGNAGE_TEXT_CHARS: Final = 40
"""Mirrors ``SignageSpec.text``'s own ceiling, so truncation happens once,
deliberately, here - rather than as a validation error deep inside construction."""

GLAZING_ROUGHNESS: Final = 0.05
DEFAULT_ROUGHNESS: Final = 0.5
DEFAULT_METALLIC: Final = 0.0

# A fast "local preview" tier, not the renderer's maximum: this keeps one
# pipeline run within a couple of minutes on a laptop CPU. Raised once Phase 7
# gives the render worker real capacity to spend.
RENDER_RESOLUTION_X: Final = 960
RENDER_RESOLUTION_Y: Final = 540
RENDER_SAMPLES: Final = 32
CAMERA_DURATION_S: Final = 3.0
CAMERA_FPS: Final = 12


class ComposeSceneSpec:
    """Deterministically maps a brief onto one of the renderer's templates."""

    def execute(
        self,
        business: BusinessProfile,
        brief: DesignBrief,
        manifest: CapabilityManifest,
    ) -> SceneSpec:
        template = _pick_template(brief.business_id, manifest.templates)
        spec = SceneSpec(
            template_id=template.id,
            seed=brief.generation.seed,
            dimensions=DEFAULT_DIMENSIONS,
            palette=brief.palette,
            materials=_assign_materials(
                template.material_slots, brief.material_families, brief.palette
            ),
            signage=SignageSpec(text=_signage_text(business.name.value)),
            lighting=LightingSpec(preset=LightingPreset(brief.lighting_mood.value)),
            camera=CameraSpec(
                move=CameraMove(brief.camera_move),
                duration_s=CAMERA_DURATION_S,
                fps=CAMERA_FPS,
            ),
            render=_render_spec(manifest),
        )

        problems = validate_against_manifest(spec, manifest)
        if problems:
            # Both repos' capability manifests have drifted out of agreement -
            # the vocabulary that produced this brief no longer matches the
            # renderer that must build it.
            raise UpstreamError(
                f"composed scene spec for {brief.business_id!r} is not "
                f"renderable: {'; '.join(problems)}"
            )
        return spec


def _pick_template(
    business_id: str,
    templates: tuple[TemplateDescriptor, ...],
) -> TemplateDescriptor:
    # Same digest-slicing pattern as generate_design_brief.seed_for(): stable
    # across runs, but not always the first template, so a batch actually
    # exercises more than one.
    digest = hashlib.sha256(business_id.encode()).digest()
    index = int.from_bytes(digest[:4], "big") % len(templates)
    return templates[index]


def _assign_materials(
    slots: tuple[MaterialSlot, ...],
    families: tuple[str, ...],
    palette: tuple[str, ...],
) -> tuple[MaterialAssignment, ...]:
    # Cycles rather than requiring an exact count: both are already validated
    # against this same manifest by Phase 3's brief guardrails, but a brief may
    # offer fewer families/colours than a template has slots.
    return tuple(
        MaterialAssignment(
            slot=slot,
            family=families[index % len(families)],
            base_color=palette[index % len(palette)],
            roughness=GLAZING_ROUGHNESS if slot is MaterialSlot.GLAZING else DEFAULT_ROUGHNESS,
            metallic=DEFAULT_METALLIC,
        )
        for index, slot in enumerate(slots)
    )


def _signage_text(name: str) -> str:
    if len(name) <= MAX_SIGNAGE_TEXT_CHARS:
        return name
    return name[: MAX_SIGNAGE_TEXT_CHARS - 1] + "…"


def _render_spec(manifest: CapabilityManifest) -> RenderSpec:
    engine = RenderEngine.EEVEE if RenderEngine.EEVEE in manifest.engines else manifest.engines[0]
    return RenderSpec(
        engine=engine,
        samples=min(RENDER_SAMPLES, manifest.limits.max_samples),
        resolution_x=min(RENDER_RESOLUTION_X, manifest.limits.max_resolution_x),
        resolution_y=min(RENDER_RESOLUTION_Y, manifest.limits.max_resolution_y),
    )

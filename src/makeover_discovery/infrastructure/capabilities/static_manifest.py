"""The renderer vocabulary compiled into this build.

Repo B publishes the authoritative ``CapabilityManifest`` at ``/capabilities``,
but it is not deployed yet, and Phases 1-3 must be demonstrable without it. This
mirrors Repo B's Phase 0 manifest so a brief can be generated and validated
offline; ``MAKEOVER_RENDER_SERVICE_URL`` switches to the live one.

Duplicating the values rather than importing them is the point: neither repo
imports the other, and the contract package - not this constant - is what keeps
the two in agreement.
"""

from __future__ import annotations

from typing import Final

from makeover_contracts.capability import (
    CapabilityManifest,
    RenderLimits,
    TemplateDescriptor,
)
from makeover_contracts.scene import (
    CameraMove,
    LightingPreset,
    MaterialSlot,
    RenderEngine,
)

FALLBACK_ENGINE_VERSION: Final = "unknown"
"""Honest about what it is: no renderer answered, so no build was reported."""

_TEMPLATES: Final = (
    TemplateDescriptor(
        id="shophouse-narrow",
        label="Narrow shophouse",
        description="Two-storey shophouse frontage with awning and hanging sign.",
        material_slots=(
            MaterialSlot.FACADE,
            MaterialSlot.TRIM,
            MaterialSlot.SIGN,
            MaterialSlot.GLAZING,
            MaterialSlot.AWNING,
            MaterialSlot.GROUND,
        ),
    ),
    TemplateDescriptor(
        id="unit-storefront",
        label="Single-unit storefront",
        description="Flat modern shopfront with a full-width glazed bay.",
        material_slots=(
            MaterialSlot.FACADE,
            MaterialSlot.TRIM,
            MaterialSlot.SIGN,
            MaterialSlot.GLAZING,
            MaterialSlot.GROUND,
        ),
    ),
)

_MATERIAL_FAMILIES: Final = ("timber", "brass", "render", "terrazzo", "steel", "glass")

_LIMITS: Final = RenderLimits(
    max_duration_s=10.0,
    max_fps=30,
    max_frame_count=300,
    max_resolution_x=1920,
    max_resolution_y=1080,
    max_samples=256,
)

BUILTIN_MANIFEST: Final = CapabilityManifest(
    renderer_name="makeover-render",
    engine_version=FALLBACK_ENGINE_VERSION,
    templates=_TEMPLATES,
    material_families=_MATERIAL_FAMILIES,
    lighting_presets=tuple(LightingPreset),
    camera_moves=tuple(CameraMove),
    engines=(RenderEngine.EEVEE, RenderEngine.CYCLES),
    limits=_LIMITS,
)


class StaticCapabilitySource:
    """Serves the compiled-in manifest, for when no renderer is reachable."""

    def __init__(self, manifest: CapabilityManifest = BUILTIN_MANIFEST) -> None:
        self._manifest = manifest

    async def manifest(self) -> CapabilityManifest:
        return self._manifest

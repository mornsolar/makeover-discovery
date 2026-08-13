"""Versioned data contracts shared by ``makeover-discovery`` and ``makeover-render``.

This package is the only thing the two repositories agree on. It holds no I/O,
no framework code, and no dependency beyond pydantic, so either side can adopt a
new version without inheriting the other's stack.
"""

from __future__ import annotations

from makeover_contracts.brief import (
    BriefGeneration,
    DesignBrief,
    LightingMood,
    SignageBrief,
)
from makeover_contracts.business import (
    BusinessCandidate,
    BusinessCategory,
    BusinessProfile,
)
from makeover_contracts.capability import (
    CapabilityManifest,
    RenderLimits,
    TemplateDescriptor,
    validate_against_manifest,
)
from makeover_contracts.geo import (
    CircleArea,
    GeoArea,
    GeoPoint,
    PolygonArea,
    Postcode,
)
from makeover_contracts.jobs import (
    ArtifactBundle,
    ArtifactKind,
    ArtifactRef,
    JobStatus,
    RenderJob,
)
from makeover_contracts.primitives import HexColor, Sha256, Slug, UnitInterval
from makeover_contracts.provenance import (
    ATTRIBUTION_TEXT,
    DataLicense,
    DataSource,
    Provenanced,
    SourceRef,
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
from makeover_contracts.version import CONTRACT_VERSION, is_compatible

__all__ = [
    "ATTRIBUTION_TEXT",
    "CONTRACT_VERSION",
    "ArtifactBundle",
    "ArtifactKind",
    "ArtifactRef",
    "BriefGeneration",
    "BusinessCandidate",
    "BusinessCategory",
    "BusinessProfile",
    "CameraMove",
    "CameraSpec",
    "CapabilityManifest",
    "CircleArea",
    "DataLicense",
    "DataSource",
    "DesignBrief",
    "GeoArea",
    "GeoPoint",
    "HexColor",
    "JobStatus",
    "LightingMood",
    "LightingPreset",
    "LightingSpec",
    "MaterialAssignment",
    "MaterialSlot",
    "PolygonArea",
    "Postcode",
    "Provenanced",
    "RenderEngine",
    "RenderJob",
    "RenderLimits",
    "RenderSpec",
    "SceneSpec",
    "Sha256",
    "SignageBrief",
    "SignageSpec",
    "Slug",
    "SourceRef",
    "StorefrontDimensions",
    "TemplateDescriptor",
    "UnitInterval",
    "is_compatible",
    "validate_against_manifest",
]

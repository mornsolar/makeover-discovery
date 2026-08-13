"""The LLM-inferred design brief.

This is the one artifact in the system produced by a model rather than derived
deterministically, so it records exactly which model and prompt produced it.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from makeover_contracts.primitives import HexColor, Slug
from makeover_contracts.version import CONTRACT_VERSION

MIN_PALETTE_COLORS = 2
MAX_PALETTE_COLORS = 6
MAX_SIGNAGE_CHARS = 40
MAX_SEED = 2**31 - 1


class LightingMood(StrEnum):
    """Art-direction intent, later mapped onto a concrete lighting rig."""

    WARM_EVENING = "warm_evening"
    BRIGHT_DAYLIGHT = "bright_daylight"
    NEON_NIGHT = "neon_night"
    SOFT_OVERCAST = "soft_overcast"


class SignageBrief(BaseModel):
    """What the storefront sign should say and how it should feel."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str = Field(min_length=1, max_length=MAX_SIGNAGE_CHARS)
    tone: str = Field(min_length=3, max_length=80)

    @field_validator("text")
    @classmethod
    def _reject_urls(cls, value: str) -> str:
        # Signage is set in 3D type, so a URL is wrong for the medium — and it
        # is a common way for injected content to reach a rendered surface.
        lowered = value.lower()
        if "http://" in lowered or "https://" in lowered or "www." in lowered:
            raise ValueError("signage text must not contain a URL")
        return value


class BriefGeneration(BaseModel):
    """Reproducibility metadata for a generated brief."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model: str = Field(min_length=1, max_length=128)
    prompt_version: str = Field(min_length=1, max_length=32)
    seed: int = Field(ge=0, le=MAX_SEED)
    generated_at: datetime

    @field_validator("generated_at")
    @classmethod
    def _require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")
        return value


class DesignBrief(BaseModel):
    """Art direction for one business, constrained to the renderer's vocabulary.

    ``material_families`` and ``camera_move`` are plain strings rather than
    enums: the authoritative list lives in the renderer's ``CapabilityManifest``
    and is checked against it at compose time. That keeps this package from
    needing a release every time the renderer gains a material.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_version: str = CONTRACT_VERSION
    business_id: Slug
    style_direction: str = Field(min_length=10, max_length=400)
    palette: tuple[HexColor, ...] = Field(
        min_length=MIN_PALETTE_COLORS, max_length=MAX_PALETTE_COLORS
    )
    material_families: tuple[str, ...] = Field(min_length=1, max_length=6)
    signage: SignageBrief
    lighting_mood: LightingMood
    camera_move: str = Field(min_length=1, max_length=64)
    rationale: str = Field(min_length=10, max_length=1000)
    do_not_include: tuple[str, ...] = Field(
        default=(),
        max_length=12,
        description="Things the render must avoid, e.g. real logos or brand marks.",
    )
    generation: BriefGeneration

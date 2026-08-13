"""Inputs and outputs of design-brief generation.

The vocabulary a brief may use is not fixed here: it is read off the renderer's
``CapabilityManifest`` at request time. That is what stops this repository from
inventing a material or a camera move that Repo B cannot render, without either
repository importing the other.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from makeover_contracts.brief import DesignBrief, LightingMood
from makeover_contracts.business import BusinessProfile
from makeover_contracts.capability import CapabilityManifest

from makeover_discovery.domain.model.llm import TokenUsage

MANDATORY_EXCLUSIONS: tuple[str, ...] = (
    "real or trademarked logos, wordmarks, and brand marks",
    "invented factual claims about the business",
    "text or signage naming a person",
)
"""Appended to every brief by the use case rather than requested from the model.

The compliance concern recorded in the roadmap - depicting real businesses that
never consented - is not something a prompt should be trusted to remember.
"""


@dataclass(frozen=True)
class BriefVocabulary:
    """The words a brief is allowed to use, projected from a manifest."""

    material_families: tuple[str, ...]
    camera_moves: tuple[str, ...]
    lighting_moods: tuple[LightingMood, ...]

    @classmethod
    def from_manifest(cls, manifest: CapabilityManifest) -> BriefVocabulary:
        presets = {preset.value for preset in manifest.lighting_presets}
        return cls(
            material_families=tuple(manifest.material_families),
            camera_moves=tuple(move.value for move in manifest.camera_moves),
            # Mood and preset are separate types on purpose - intent versus
            # implementation - so a mood is only offerable when the renderer
            # ships a rig that realises it.
            lighting_moods=tuple(mood for mood in LightingMood if mood.value in presets),
        )


@dataclass(frozen=True)
class BriefRequest:
    """Everything a generator needs for one attempt at a brief."""

    profile: BusinessProfile
    vocabulary: BriefVocabulary
    seed: int
    problems: tuple[str, ...] = field(default=())
    """Why the previous attempt was rejected. Empty on a first attempt."""


@dataclass(frozen=True)
class GeneratedBrief:
    """A brief plus what it cost to produce it."""

    brief: DesignBrief
    usage: TokenUsage


@dataclass(frozen=True)
class BriefResult:
    """The outcome of the use case: a valid brief, its spend, and its history."""

    brief: DesignBrief
    usage: TokenUsage
    cost_usd: float
    attempts: int
    repaired_problems: tuple[str, ...] = ()
    """Problems that a repair round fixed. Empty when the first attempt passed."""

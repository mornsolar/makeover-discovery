"""A persisted, publishable unit of work: one business's pipeline result plus
whatever this repo has decided about showing it to the world.

Layered on top of ``PipelineResult`` rather than replacing it - the pipeline
producing a render is a different concern from persisting, publishing, or
taking one down, and keeping them separate is what lets ``PublishProject``
and ``TakedownProject`` stay pure persistence operations with no filesystem
or rendering knowledge of their own.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from makeover_discovery.domain.model.pipeline import PipelineResult


class BeforeImageSource(StrEnum):
    AUTO_PHOTO = "auto_photo"
    MANUAL_UPLOAD = "manual_upload"


@dataclass(frozen=True)
class BeforeImage:
    uri: str
    source: BeforeImageSource
    attribution: str | None = None
    """Carried over from the photo's own ``SourceRef`` when auto-picked; a
    manual upload has no such provenance to attribute."""


@dataclass(frozen=True)
class Project:
    """One business's makeover: its pipeline result, its before-image (once
    sourced), and whether it may be shown to anyone.

    ``id`` is the business's own id, not a separately generated one - the
    pipeline is already deterministic per business, so a re-run is meant to
    upsert the same project rather than accumulate duplicates.
    """

    id: str
    pipeline: PipelineResult
    before_image: BeforeImage | None
    created_at: datetime
    published: bool = False
    takedown: bool = False
    """Per the roadmap's compliance gate: hard-disables a published page,
    independent of ``published`` - a takedown must not be undoable by
    publishing again without a deliberate, separate action."""

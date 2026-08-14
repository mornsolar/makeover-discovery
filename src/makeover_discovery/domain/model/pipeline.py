"""Outcome of running one business through the full makeover pipeline.

This is the use case's own vocabulary, not part of ``makeover-contracts`` -
Repo B has no business knowing a pipeline exists, exactly like ``discovery.py``
keeps postcode vocabulary out of the ``BusinessDirectory`` port.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from makeover_contracts.brief import DesignBrief
from makeover_contracts.business import BusinessProfile
from makeover_contracts.jobs import RenderJob
from makeover_contracts.scene import SceneSpec


class PipelineOutcome(StrEnum):
    """What happened for one business.

    Recorded rather than raised: a batch run processes several businesses, and
    one business's brief or render failure must not discard the others'
    results - the same reasoning behind ``EnrichBusinessProfile``'s
    ``WebsiteOutcome``.
    """

    RENDERED = "rendered"
    BRIEF_FAILED = "brief_failed"
    RENDER_FAILED = "render_failed"


@dataclass(frozen=True)
class PipelineResult:
    """One business's outcome: what it produced, and how far it got."""

    business: BusinessProfile
    outcome: PipelineOutcome
    brief: DesignBrief | None = None
    scene_spec: SceneSpec | None = None
    render_job: RenderJob | None = None
    error: str | None = None

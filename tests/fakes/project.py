"""Builders for ``PipelineResult``/``Project`` fixtures."""

from __future__ import annotations

from datetime import UTC, datetime

from makeover_contracts.business import BusinessProfile

from makeover_discovery.domain.model.pipeline import PipelineOutcome, PipelineResult
from makeover_discovery.domain.model.project import BeforeImage, Project
from tests.fakes.brief import make_brief, make_profile
from tests.fakes.render_client import make_render_job
from tests.fakes.specs import make_scene_spec

CREATED_AT = datetime(2026, 8, 14, 9, 0, tzinfo=UTC)


def make_pipeline_result(
    business: BusinessProfile | None = None,
    *,
    outcome: PipelineOutcome = PipelineOutcome.RENDERED,
    with_artifacts: bool = True,
) -> PipelineResult:
    business = business or make_profile()
    if outcome is not PipelineOutcome.RENDERED:
        return PipelineResult(business=business, outcome=outcome, error="boom")
    brief = make_brief(business)
    spec = make_scene_spec()
    job = make_render_job(spec, job_id=f"job-{business.id}") if with_artifacts else None
    return PipelineResult(
        business=business, outcome=outcome, brief=brief, scene_spec=spec, render_job=job
    )


def make_project(
    *,
    business: BusinessProfile | None = None,
    outcome: PipelineOutcome = PipelineOutcome.RENDERED,
    before_image: BeforeImage | None = None,
    published: bool = False,
    takedown: bool = False,
    created_at: datetime = CREATED_AT,
) -> Project:
    business = business or make_profile()
    return Project(
        id=business.id,
        pipeline=make_pipeline_result(business, outcome=outcome),
        before_image=before_image,
        created_at=created_at,
        published=published,
        takedown=takedown,
    )

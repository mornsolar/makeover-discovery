"""SQLAlchemy-backed ``ProjectRepository``."""

from __future__ import annotations

from makeover_contracts.brief import DesignBrief
from makeover_contracts.business import BusinessProfile
from makeover_contracts.jobs import RenderJob
from makeover_contracts.scene import SceneSpec
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from makeover_discovery.domain.model.pipeline import PipelineOutcome, PipelineResult
from makeover_discovery.domain.model.project import BeforeImage, BeforeImageSource, Project
from makeover_discovery.infrastructure.persistence.models import ProjectRow


class SqlAlchemyProjectRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save(self, project: Project) -> None:
        row = _to_row(project)
        async with self._session_factory() as session:
            await session.merge(row)
            await session.commit()

    async def get(self, project_id: str) -> Project | None:
        async with self._session_factory() as session:
            row = await session.get(ProjectRow, project_id)
        return _to_domain(row) if row is not None else None


def _to_row(project: Project) -> ProjectRow:
    pipeline = project.pipeline
    before = project.before_image
    return ProjectRow(
        id=project.id,
        business_json=pipeline.business.model_dump_json(),
        outcome=pipeline.outcome.value,
        brief_json=pipeline.brief.model_dump_json() if pipeline.brief is not None else None,
        scene_spec_json=(
            pipeline.scene_spec.model_dump_json() if pipeline.scene_spec is not None else None
        ),
        render_job_json=(
            pipeline.render_job.model_dump_json() if pipeline.render_job is not None else None
        ),
        pipeline_error=pipeline.error,
        before_image_uri=before.uri if before is not None else None,
        before_image_source=before.source.value if before is not None else None,
        before_image_attribution=before.attribution if before is not None else None,
        published=project.published,
        takedown=project.takedown,
        created_at=project.created_at,
    )


def _to_domain(row: ProjectRow) -> Project:
    before_image = None
    if row.before_image_uri is not None and row.before_image_source is not None:
        before_image = BeforeImage(
            uri=row.before_image_uri,
            source=BeforeImageSource(row.before_image_source),
            attribution=row.before_image_attribution,
        )
    pipeline = PipelineResult(
        business=BusinessProfile.model_validate_json(row.business_json),
        outcome=PipelineOutcome(row.outcome),
        brief=DesignBrief.model_validate_json(row.brief_json) if row.brief_json else None,
        scene_spec=(
            SceneSpec.model_validate_json(row.scene_spec_json) if row.scene_spec_json else None
        ),
        render_job=(
            RenderJob.model_validate_json(row.render_job_json) if row.render_job_json else None
        ),
        error=row.pipeline_error,
    )
    return Project(
        id=row.id,
        pipeline=pipeline,
        before_image=before_image,
        created_at=row.created_at,
        published=row.published,
        takedown=row.takedown,
    )

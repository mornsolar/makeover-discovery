"""Project lifecycle endpoints: run the pipeline, fetch, upload a before
image, publish, and take one down.

Domain errors (``NotFoundError``, ``ValidationError``, ...) are left to
propagate to the central handler registered in ``interfaces/api/errors.py``
rather than translated here - the same convention every other router in this
service follows.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, UploadFile
from makeover_contracts.brief import DesignBrief
from makeover_contracts.business import BusinessProfile
from makeover_contracts.jobs import ArtifactBundle
from makeover_contracts.scene import SceneSpec
from pydantic import BaseModel, ConfigDict

from makeover_discovery.domain.errors import NotFoundError
from makeover_discovery.domain.model.discovery import DiscoveryQuery
from makeover_discovery.domain.model.pipeline import PipelineOutcome
from makeover_discovery.domain.model.project import BeforeImageSource, Project
from makeover_discovery.interfaces.api.deps import (
    ProjectRepositoryDep,
    PublishProjectDep,
    RunMakeoverPipelineDep,
    SaveProjectDep,
    TakedownProjectDep,
    UploadBeforeImageDep,
)

router = APIRouter(tags=["projects"])

_DEFAULT_UPLOAD_FILENAME = "before"
_DEFAULT_UPLOAD_MEDIA_TYPE = "application/octet-stream"


class BeforeImageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    uri: str
    source: BeforeImageSource
    attribution: str | None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    outcome: PipelineOutcome
    business: BusinessProfile
    brief: DesignBrief | None
    scene_spec: SceneSpec | None
    artifacts: ArtifactBundle | None
    error: str | None
    before_image: BeforeImageResponse | None
    published: bool
    takedown: bool
    created_at: datetime


def _to_response(project: Project) -> ProjectResponse:
    pipeline = project.pipeline
    before = project.before_image
    return ProjectResponse(
        id=project.id,
        outcome=pipeline.outcome,
        business=pipeline.business,
        brief=pipeline.brief,
        scene_spec=pipeline.scene_spec,
        artifacts=pipeline.render_job.artifacts if pipeline.render_job is not None else None,
        error=pipeline.error,
        before_image=(
            BeforeImageResponse(
                uri=before.uri, source=before.source, attribution=before.attribution
            )
            if before is not None
            else None
        ),
        published=project.published,
        takedown=project.takedown,
        created_at=project.created_at,
    )


@router.post(
    "/projects",
    response_model=tuple[ProjectResponse, ...],
    summary="Run the makeover pipeline for a postcode and save the results",
)
async def create_projects(
    query: DiscoveryQuery,
    pipeline: RunMakeoverPipelineDep,
    save: SaveProjectDep,
) -> tuple[ProjectResponse, ...]:
    results = await pipeline.execute(query)
    projects = [await save.execute(result) for result in results]
    return tuple(_to_response(project) for project in projects)


@router.get(
    "/projects/{project_id}", response_model=ProjectResponse, summary="Fetch a saved project"
)
async def get_project(project_id: str, repository: ProjectRepositoryDep) -> ProjectResponse:
    project = await repository.get(project_id)
    if project is None:
        raise NotFoundError(f"no project {project_id!r}")
    return _to_response(project)


@router.post(
    "/projects/{project_id}/before-image",
    response_model=ProjectResponse,
    summary="Manually upload a before-image for a project OSM had none for",
)
async def upload_before_image(
    project_id: str,
    file: UploadFile,
    use_case: UploadBeforeImageDep,
) -> ProjectResponse:
    data = await file.read()
    project = await use_case.execute(
        project_id,
        data,
        filename=file.filename or _DEFAULT_UPLOAD_FILENAME,
        media_type=file.content_type or _DEFAULT_UPLOAD_MEDIA_TYPE,
    )
    return _to_response(project)


@router.post(
    "/projects/{project_id}/publish", response_model=ProjectResponse, summary="Publish a project"
)
async def publish_project(project_id: str, use_case: PublishProjectDep) -> ProjectResponse:
    return _to_response(await use_case.execute(project_id))


@router.post(
    "/projects/{project_id}/takedown",
    response_model=ProjectResponse,
    summary="Hard-disable a project, published or not",
)
async def takedown_project(project_id: str, use_case: TakedownProjectDep) -> ProjectResponse:
    return _to_response(await use_case.execute(project_id))

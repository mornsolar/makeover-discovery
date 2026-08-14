"""Flips a project from private/draft to publishable.

Pure persistence - this use case never touches the filesystem or knows
about an ``--out`` directory. Regenerating the on-disk landing page after a
publish is the caller's job (CLI/API), the same way every other use case in
this repo stays a single responsibility.
"""

from __future__ import annotations

import dataclasses

from makeover_discovery.application.ports.project_repository import ProjectRepository
from makeover_discovery.domain.errors import NotFoundError, ValidationError
from makeover_discovery.domain.model.pipeline import PipelineOutcome
from makeover_discovery.domain.model.project import Project


class PublishProject:
    def __init__(self, repository: ProjectRepository) -> None:
        self._repository = repository

    async def execute(self, project_id: str) -> Project:
        project = await self._repository.get(project_id)
        if project is None:
            raise NotFoundError(f"no project {project_id!r}")
        if project.takedown:
            # A takedown must not be undoable by publishing again without a
            # deliberate, separate reversal - there is none yet.
            raise ValidationError(f"project {project_id!r} was taken down; refusing to publish")
        if project.pipeline.outcome is not PipelineOutcome.RENDERED:
            raise ValidationError(f"project {project_id!r} has no successful render to publish")
        if project.before_image is None:
            raise ValidationError(f"project {project_id!r} has no before-image to publish")

        updated = dataclasses.replace(project, published=True)
        await self._repository.save(updated)
        return updated

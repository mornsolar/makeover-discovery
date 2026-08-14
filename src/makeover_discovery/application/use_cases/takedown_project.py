"""The roadmap's stated compliance gate: hard-disables a published page."""

from __future__ import annotations

import dataclasses

from makeover_discovery.application.ports.project_repository import ProjectRepository
from makeover_discovery.domain.errors import NotFoundError
from makeover_discovery.domain.model.project import Project


class TakedownProject:
    def __init__(self, repository: ProjectRepository) -> None:
        self._repository = repository

    async def execute(self, project_id: str) -> Project:
        project = await self._repository.get(project_id)
        if project is None:
            raise NotFoundError(f"no project {project_id!r}")

        updated = dataclasses.replace(project, published=False, takedown=True)
        await self._repository.save(updated)
        return updated

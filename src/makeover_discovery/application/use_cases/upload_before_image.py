"""The manual before-image fallback, for a business OSM had no photo for."""

from __future__ import annotations

import dataclasses

from makeover_discovery.application.ports.artifact_store import ArtifactStore
from makeover_discovery.application.ports.project_repository import ProjectRepository
from makeover_discovery.domain.errors import NotFoundError
from makeover_discovery.domain.model.project import BeforeImage, BeforeImageSource, Project


class UploadBeforeImage:
    def __init__(self, repository: ProjectRepository, artifact_store: ArtifactStore) -> None:
        self._repository = repository
        self._artifact_store = artifact_store

    async def execute(
        self,
        project_id: str,
        data: bytes,
        *,
        filename: str,
        media_type: str,
    ) -> Project:
        project = await self._repository.get(project_id)
        if project is None:
            raise NotFoundError(f"no project {project_id!r}")

        stored = await self._artifact_store.store_bytes(data, project_id, filename, media_type)
        updated = dataclasses.replace(
            project,
            before_image=BeforeImage(uri=stored.uri, source=BeforeImageSource.MANUAL_UPLOAD),
        )
        await self._repository.save(updated)
        return updated

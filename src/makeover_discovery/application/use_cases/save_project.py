"""Turns one pipeline result into a persisted, before-image-sourced project."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from makeover_contracts.business import BusinessProfile
from makeover_contracts.jobs import ArtifactBundle, ArtifactRef

from makeover_discovery.application.ports.artifact_store import ArtifactStore
from makeover_discovery.application.ports.clock import Clock
from makeover_discovery.application.ports.project_repository import ProjectRepository
from makeover_discovery.domain.model.pipeline import PipelineResult
from makeover_discovery.domain.model.project import BeforeImage, BeforeImageSource, Project


class SaveProject:
    """Copies a rendered pipeline result's artifacts into this repo's own
    storage, auto-picks a before-image when one is available, and persists
    the result - whether or not the render actually succeeded, so a failed
    attempt is still visible rather than silently discarded."""

    def __init__(
        self,
        repository: ProjectRepository,
        artifact_store: ArtifactStore,
        clock: Clock,
    ) -> None:
        self._repository = repository
        self._artifact_store = artifact_store
        self._clock = clock

    async def execute(self, result: PipelineResult) -> Project:
        project_id = result.business.id
        pipeline = result
        if result.render_job is not None and result.render_job.artifacts is not None:
            copied = await self._copy_artifacts(project_id, result.render_job.artifacts)
            updated_job = result.render_job.model_copy(update={"artifacts": copied})
            pipeline = dataclasses.replace(result, render_job=updated_job)

        project = Project(
            id=project_id,
            pipeline=pipeline,
            before_image=_auto_before_image(result.business),
            # The most recent successful save, not necessarily the first ever
            # one - the pipeline is deterministic per business, so a re-run is
            # meant to replace rather than accumulate a history.
            created_at=self._clock.now(),
        )
        await self._repository.save(project)
        return project

    async def _copy_artifacts(self, project_id: str, bundle: ArtifactBundle) -> ArtifactBundle:
        stills = tuple(
            [
                await self._copy_ref(project_id, still, f"still_{index}.png")
                for index, still in enumerate(bundle.stills)
            ]
        )
        return ArtifactBundle(
            gltf=await self._copy_ref(project_id, bundle.gltf, "scene.glb"),
            video=await self._copy_ref(project_id, bundle.video, "animation.mp4"),
            thumbnail=await self._copy_ref(project_id, bundle.thumbnail, "thumbnail.png"),
            stills=stills,
        )

    async def _copy_ref(self, project_id: str, ref: ArtifactRef, filename: str) -> ArtifactRef:
        # Repo B already computed size/hash for these bytes; copying them
        # verbatim doesn't need to redo that work, only relocate them under
        # this repo's own durable storage.
        stored = await self._artifact_store.store_file(Path(ref.uri), project_id, filename)
        return ArtifactRef(
            kind=ref.kind,
            uri=stored.uri,
            media_type=ref.media_type,
            size_bytes=ref.size_bytes,
            sha256=ref.sha256,
        )


def _auto_before_image(business: BusinessProfile) -> BeforeImage | None:
    if not business.photo_urls:
        return None
    photo = business.photo_urls[0]
    return BeforeImage(
        uri=photo.value,
        source=BeforeImageSource.AUTO_PHOTO,
        attribution=photo.source.attribution,
    )

"""Turns one pipeline result into a persisted, before-image-sourced project."""

from __future__ import annotations

import dataclasses
import hashlib

from makeover_contracts.business import BusinessProfile
from makeover_contracts.jobs import ArtifactBundle, ArtifactRef

from makeover_discovery.application.ports.artifact_store import ArtifactStore
from makeover_discovery.application.ports.clock import Clock
from makeover_discovery.application.ports.project_repository import ProjectRepository
from makeover_discovery.application.ports.render_client import RenderClient
from makeover_discovery.domain.errors import UpstreamError
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
        render_client: RenderClient,
    ) -> None:
        self._repository = repository
        self._artifact_store = artifact_store
        self._clock = clock
        self._render_client = render_client

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
        # ref.uri is a path on Repo B's own API, not this process's own
        # filesystem - the two services never share a disk, so the bytes have
        # to come over HTTP rather than a local file read.
        data = await self._render_client.fetch_artifact(ref.uri)
        digest = hashlib.sha256(data).hexdigest()
        if digest != ref.sha256:
            # The digest is exactly what ArtifactRef carries it for: proof of
            # what was actually fetched, not just what the job record claims.
            raise UpstreamError(f"downloaded {filename} does not match the sha256 the job reported")
        stored = await self._artifact_store.store_bytes(data, project_id, filename, ref.media_type)
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

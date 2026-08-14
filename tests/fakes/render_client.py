"""Builders and a fake for the render-job client."""

from __future__ import annotations

from datetime import UTC, datetime

from makeover_contracts.jobs import ArtifactBundle, ArtifactKind, ArtifactRef, JobStatus, RenderJob
from makeover_contracts.scene import SceneSpec

SUBMITTED_AT = datetime(2026, 8, 13, 9, 30, tzinfo=UTC)
FINISHED_AT = datetime(2026, 8, 13, 9, 35, tzinfo=UTC)


def _artifact_ref(kind: ArtifactKind) -> ArtifactRef:
    return ArtifactRef(
        kind=kind,
        uri=f"/out/{kind.value}",
        media_type="application/octet-stream",
        size_bytes=1,
        sha256="a" * 64,
    )


def make_artifact_bundle() -> ArtifactBundle:
    return ArtifactBundle(
        gltf=_artifact_ref(ArtifactKind.GLTF),
        video=_artifact_ref(ArtifactKind.VIDEO),
        thumbnail=_artifact_ref(ArtifactKind.THUMBNAIL),
    )


def make_render_job(
    spec: SceneSpec,
    *,
    job_id: str = "job-1",
    status: JobStatus = JobStatus.SUCCEEDED,
    error: str | None = None,
    artifacts: ArtifactBundle | None = None,
) -> RenderJob:
    if status is JobStatus.SUCCEEDED and artifacts is None:
        artifacts = make_artifact_bundle()
    if status is JobStatus.FAILED and error is None:
        error = "render failed"
    return RenderJob(
        id=job_id,
        spec=spec,
        status=status,
        created_at=SUBMITTED_AT,
        finished_at=FINISHED_AT if status.is_terminal else None,
        error=error,
        artifacts=artifacts,
    )


class FakeRenderClient:
    """Records every submitted spec; ``poll`` steps through a scripted
    sequence of jobs so tests can simulate queued -> running -> succeeded (or
    a job that never terminates, for timeout tests) without any real wait."""

    def __init__(self, poll_sequence: list[RenderJob] | None = None) -> None:
        self._poll_sequence = poll_sequence
        self.submitted: list[SceneSpec] = []
        self._poll_calls = 0

    async def submit(self, spec: SceneSpec) -> RenderJob:
        self.submitted.append(spec)
        return make_render_job(spec, status=JobStatus.QUEUED)

    async def poll(self, job_id: str) -> RenderJob:
        if self._poll_sequence is None:
            raise AssertionError("FakeRenderClient.poll called without a scripted sequence")
        index = min(self._poll_calls, len(self._poll_sequence) - 1)
        self._poll_calls += 1
        return self._poll_sequence[index]

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from makeover_contracts.jobs import (
    ArtifactBundle,
    ArtifactKind,
    ArtifactRef,
    JobStatus,
    RenderJob,
)
from makeover_contracts.scene import (
    CameraMove,
    CameraSpec,
    LightingPreset,
    LightingSpec,
    MaterialAssignment,
    MaterialSlot,
    SceneSpec,
    SignageSpec,
    StorefrontDimensions,
)
from pydantic import ValidationError

CREATED_AT = datetime(2026, 8, 13, 9, 0, tzinfo=UTC)
DIGEST = "a" * 64

SPEC = SceneSpec(
    template_id="shophouse-narrow",
    seed=1,
    dimensions=StorefrontDimensions(width_m=8.0, height_m=4.5, depth_m=6.0),
    palette=("#1B4D3E",),
    materials=(
        MaterialAssignment(slot=MaterialSlot.FACADE, family="timber", base_color="#1B4D3E"),
    ),
    signage=SignageSpec(text="KEDAI KOPI"),
    lighting=LightingSpec(preset=LightingPreset.WARM_EVENING),
    camera=CameraSpec(move=CameraMove.ORBIT),
)


def artifact(kind: ArtifactKind, media_type: str) -> ArtifactRef:
    return ArtifactRef(
        kind=kind,
        uri=f"file:///out/{kind.value}",
        media_type=media_type,
        size_bytes=1,
        sha256=DIGEST,
    )


BUNDLE = ArtifactBundle(
    gltf=artifact(ArtifactKind.GLTF, "model/gltf-binary"),
    video=artifact(ArtifactKind.VIDEO, "video/mp4"),
    thumbnail=artifact(ArtifactKind.THUMBNAIL, "image/png"),
)


def make_job(**overrides) -> RenderJob:
    defaults = {"id": "job-1", "spec": SPEC, "status": JobStatus.QUEUED, "created_at": CREATED_AT}
    return RenderJob(**{**defaults, **overrides})


class TestJobStatus:
    @pytest.mark.parametrize("status", [JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED])
    def test_terminal_statuses_are_flagged(self, status):
        assert status.is_terminal is True

    @pytest.mark.parametrize("status", [JobStatus.QUEUED, JobStatus.RUNNING])
    def test_in_flight_statuses_are_not_terminal(self, status):
        assert status.is_terminal is False


class TestArtifactBundle:
    def test_rejects_a_bundle_whose_slots_hold_the_wrong_kind(self):
        with pytest.raises(ValidationError, match="expected a gltf artifact"):
            ArtifactBundle(
                gltf=artifact(ArtifactKind.VIDEO, "video/mp4"),
                video=artifact(ArtifactKind.VIDEO, "video/mp4"),
                thumbnail=artifact(ArtifactKind.THUMBNAIL, "image/png"),
            )

    def test_rejects_a_non_still_inside_stills(self):
        with pytest.raises(ValidationError, match="must be a still artifact"):
            ArtifactBundle(
                gltf=artifact(ArtifactKind.GLTF, "model/gltf-binary"),
                video=artifact(ArtifactKind.VIDEO, "video/mp4"),
                thumbnail=artifact(ArtifactKind.THUMBNAIL, "image/png"),
                stills=(artifact(ArtifactKind.VIDEO, "video/mp4"),),
            )

    def test_rejects_a_malformed_digest(self):
        with pytest.raises(ValidationError):
            ArtifactRef(
                kind=ArtifactKind.GLTF,
                uri="file:///out/x",
                media_type="model/gltf-binary",
                size_bytes=1,
                sha256="not-a-digest",
            )


class TestRenderJobLifecycle:
    def test_accepts_a_queued_job_without_timings(self):
        assert make_job().status is JobStatus.QUEUED

    def test_requires_finished_at_on_a_terminal_job(self):
        with pytest.raises(ValidationError, match="must have finished_at"):
            make_job(status=JobStatus.SUCCEEDED, artifacts=BUNDLE)

    def test_rejects_finished_at_on_an_in_flight_job(self):
        with pytest.raises(ValidationError, match="must not have finished_at"):
            make_job(status=JobStatus.RUNNING, finished_at=CREATED_AT)

    def test_requires_artifacts_on_success(self):
        with pytest.raises(ValidationError, match="must carry artifacts"):
            make_job(status=JobStatus.SUCCEEDED, finished_at=CREATED_AT)

    def test_requires_an_error_on_failure(self):
        with pytest.raises(ValidationError, match="must carry an error"):
            make_job(status=JobStatus.FAILED, finished_at=CREATED_AT)

    def test_rejects_a_finish_before_the_start(self):
        with pytest.raises(ValidationError, match="must not precede started_at"):
            make_job(
                status=JobStatus.SUCCEEDED,
                started_at=CREATED_AT + timedelta(minutes=5),
                finished_at=CREATED_AT + timedelta(minutes=1),
                artifacts=BUNDLE,
            )

    def test_accepts_a_well_formed_successful_job(self):
        job = make_job(
            status=JobStatus.SUCCEEDED,
            started_at=CREATED_AT,
            finished_at=CREATED_AT + timedelta(minutes=2),
            artifacts=BUNDLE,
        )
        assert job.artifacts is not None

    def test_rejects_a_naive_created_at(self):
        with pytest.raises(ValidationError, match="timezone-aware"):
            make_job(created_at=datetime(2026, 8, 13, 9, 0))

"""Render job lifecycle and produced artifacts.

The model validators here encode the invariants that make a job record
trustworthy: a finished job has a finish time, a successful one has artifacts,
and a failed one has a reason.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from makeover_contracts.primitives import Sha256
from makeover_contracts.scene import SceneSpec


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self in _TERMINAL_STATUSES


_TERMINAL_STATUSES = frozenset({JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED})


class ArtifactKind(StrEnum):
    GLTF = "gltf"
    VIDEO = "video"
    STILL = "still"
    THUMBNAIL = "thumbnail"


class ArtifactRef(BaseModel):
    """A pointer to one produced file.

    Carries a digest so the discovery repo can verify what it fetched rather
    than trusting the URI, which may be a presigned link from object storage.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: ArtifactKind
    uri: str = Field(min_length=1, max_length=2048)
    media_type: str = Field(min_length=3, max_length=128)
    size_bytes: int = Field(ge=0)
    sha256: Sha256


class ArtifactBundle(BaseModel):
    """Everything one successful render produced."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    gltf: ArtifactRef
    video: ArtifactRef
    thumbnail: ArtifactRef
    stills: tuple[ArtifactRef, ...] = ()

    @model_validator(mode="after")
    def _check_kinds(self) -> ArtifactBundle:
        expected = (
            (self.gltf, ArtifactKind.GLTF),
            (self.video, ArtifactKind.VIDEO),
            (self.thumbnail, ArtifactKind.THUMBNAIL),
        )
        for artifact, kind in expected:
            if artifact.kind is not kind:
                raise ValueError(f"expected a {kind.value} artifact, got {artifact.kind.value}")
        if any(still.kind is not ArtifactKind.STILL for still in self.stills):
            raise ValueError("every entry in stills must be a still artifact")
        return self


class RenderJob(BaseModel):
    """A unit of render work and its outcome."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    spec: SceneSpec
    status: JobStatus
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = Field(default=None, max_length=2000)
    artifacts: ArtifactBundle | None = None

    @field_validator("created_at", "started_at", "finished_at")
    @classmethod
    def _require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _check_lifecycle_invariants(self) -> RenderJob:
        if self.status.is_terminal and self.finished_at is None:
            raise ValueError(f"a {self.status.value} job must have finished_at")
        if not self.status.is_terminal and self.finished_at is not None:
            raise ValueError(f"a {self.status.value} job must not have finished_at")
        if self.status is JobStatus.SUCCEEDED and self.artifacts is None:
            raise ValueError("a succeeded job must carry artifacts")
        if self.status is JobStatus.FAILED and not self.error:
            raise ValueError("a failed job must carry an error")
        if (
            self.finished_at is not None
            and self.started_at is not None
            and self.finished_at < self.started_at
        ):
            raise ValueError("finished_at must not precede started_at")
        return self

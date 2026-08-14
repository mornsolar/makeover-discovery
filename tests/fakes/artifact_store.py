"""In-memory ``ArtifactStore`` double."""

from __future__ import annotations

from pathlib import Path

from makeover_discovery.application.ports.artifact_store import StoredArtifact

FAKE_SHA256 = "b" * 64


class FakeArtifactStore:
    def __init__(self) -> None:
        self.stored_files: list[tuple[Path, str, str]] = []
        self.stored_bytes: list[tuple[bytes, str, str, str]] = []

    async def store_file(self, source: Path, project_id: str, filename: str) -> StoredArtifact:
        self.stored_files.append((source, project_id, filename))
        size = source.stat().st_size if source.exists() else 0
        return StoredArtifact(
            uri=f"/fake-store/{project_id}/{filename}",
            media_type="application/octet-stream",
            size_bytes=size,
            sha256=FAKE_SHA256,
        )

    async def store_bytes(
        self, data: bytes, project_id: str, filename: str, media_type: str
    ) -> StoredArtifact:
        self.stored_bytes.append((data, project_id, filename, media_type))
        return StoredArtifact(
            uri=f"/fake-store/{project_id}/{filename}",
            media_type=media_type,
            size_bytes=len(data),
            sha256=FAKE_SHA256,
        )

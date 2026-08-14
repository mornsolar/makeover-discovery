"""In-memory ``ArtifactStore`` double."""

from __future__ import annotations

from makeover_discovery.application.ports.artifact_store import StoredArtifact

FAKE_SHA256 = "b" * 64


class FakeArtifactStore:
    def __init__(self) -> None:
        self.stored_bytes: list[tuple[bytes, str, str, str]] = []

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

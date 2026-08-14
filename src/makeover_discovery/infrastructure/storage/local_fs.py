"""Local-filesystem ``ArtifactStore``.

The only implementation this phase needs: this repo's own durable storage,
distinct from Repo B's - artifacts arrive as bytes over HTTP, never a shared
disk. A future object-storage adapter (S3) implements the same port without
this repo's callers changing.
"""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

from makeover_discovery.application.ports.artifact_store import StoredArtifact


class LocalFsArtifactStore:
    def __init__(self, root: Path) -> None:
        self._root = root

    async def store_bytes(
        self, data: bytes, project_id: str, filename: str, media_type: str
    ) -> StoredArtifact:
        dest_dir = self._root / project_id
        await asyncio.to_thread(dest_dir.mkdir, parents=True, exist_ok=True)
        dest = dest_dir / filename
        await asyncio.to_thread(dest.write_bytes, data)
        return StoredArtifact(
            uri=str(dest),
            media_type=media_type,
            size_bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
        )

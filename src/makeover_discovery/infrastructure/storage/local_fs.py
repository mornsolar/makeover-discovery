"""Local-filesystem ``ArtifactStore``.

The only implementation this phase needs: everything runs on one machine for
now, same as Repo B's own artifact directory. A future object-storage
adapter (S3) implements the same port without this repo's callers changing.
"""

from __future__ import annotations

import asyncio
import hashlib
import mimetypes
from pathlib import Path
from typing import Final

from makeover_discovery.application.ports.artifact_store import StoredArtifact

DEFAULT_MEDIA_TYPE: Final = "application/octet-stream"


class LocalFsArtifactStore:
    def __init__(self, root: Path) -> None:
        self._root = root

    async def store_file(self, source: Path, project_id: str, filename: str) -> StoredArtifact:
        data = await asyncio.to_thread(source.read_bytes)
        return await self._write(data, project_id, filename, _guess_media_type(filename))

    async def store_bytes(
        self, data: bytes, project_id: str, filename: str, media_type: str
    ) -> StoredArtifact:
        return await self._write(data, project_id, filename, media_type)

    async def _write(
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


def _guess_media_type(filename: str) -> str:
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or DEFAULT_MEDIA_TYPE

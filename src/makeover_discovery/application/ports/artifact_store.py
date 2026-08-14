"""Artifact storage port.

Mirrors ``makeover_contracts.jobs.ArtifactRef``'s shape (uri/media_type/
size_bytes/sha256) without importing it: this store also has to hold a plain
uploaded before-image, which isn't one of Repo B's ``ArtifactKind``s, so its
own vocabulary stays independent of the render contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class StoredArtifact:
    uri: str
    media_type: str
    size_bytes: int
    sha256: str


class ArtifactStore(Protocol):
    """Durably holds a project's files, independent of wherever they
    originated - a render fetched over HTTP, or a browser upload."""

    async def store_bytes(
        self, data: bytes, project_id: str, filename: str, media_type: str
    ) -> StoredArtifact: ...

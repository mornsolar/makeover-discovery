"""``LocalFsArtifactStore``, against a real temporary directory."""

from __future__ import annotations

import hashlib

from makeover_discovery.infrastructure.storage.local_fs import LocalFsArtifactStore


async def test_store_file_copies_bytes_and_reports_the_right_hash(tmp_path):
    source = tmp_path / "source.png"
    source.write_bytes(b"fake-png-bytes")
    store = LocalFsArtifactStore(tmp_path / "artifacts")

    stored = await store.store_file(source, "project-1", "thumbnail.png")

    dest = tmp_path / "artifacts" / "project-1" / "thumbnail.png"
    assert dest.read_bytes() == b"fake-png-bytes"
    assert stored.uri == str(dest)
    assert stored.size_bytes == len(b"fake-png-bytes")
    assert stored.sha256 == hashlib.sha256(b"fake-png-bytes").hexdigest()
    assert stored.media_type == "image/png"


async def test_store_bytes_writes_directly(tmp_path):
    store = LocalFsArtifactStore(tmp_path / "artifacts")

    stored = await store.store_bytes(b"jpeg-bytes", "project-2", "before.jpg", "image/jpeg")

    dest = tmp_path / "artifacts" / "project-2" / "before.jpg"
    assert dest.read_bytes() == b"jpeg-bytes"
    assert stored.media_type == "image/jpeg"


async def test_two_projects_do_not_collide(tmp_path):
    store = LocalFsArtifactStore(tmp_path / "artifacts")

    await store.store_bytes(b"one", "project-a", "before.jpg", "image/jpeg")
    await store.store_bytes(b"two", "project-b", "before.jpg", "image/jpeg")

    assert (tmp_path / "artifacts" / "project-a" / "before.jpg").read_bytes() == b"one"
    assert (tmp_path / "artifacts" / "project-b" / "before.jpg").read_bytes() == b"two"

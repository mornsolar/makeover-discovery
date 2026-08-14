"""``UploadBeforeImage``, against fake storage."""

from __future__ import annotations

import pytest

from makeover_discovery.application.use_cases.upload_before_image import UploadBeforeImage
from makeover_discovery.domain.errors import NotFoundError
from makeover_discovery.domain.model.project import BeforeImageSource
from tests.fakes.artifact_store import FakeArtifactStore
from tests.fakes.project import make_project
from tests.fakes.project_repository import FakeProjectRepository


async def test_raises_for_an_unknown_project():
    use_case = UploadBeforeImage(FakeProjectRepository(), FakeArtifactStore())

    with pytest.raises(NotFoundError):
        await use_case.execute("does-not-exist", b"data", filename="a.jpg", media_type="image/jpeg")


async def test_stores_the_upload_and_marks_it_manual():
    project = make_project(before_image=None)
    repository = FakeProjectRepository((project,))
    artifact_store = FakeArtifactStore()
    use_case = UploadBeforeImage(repository, artifact_store)

    updated = await use_case.execute(
        project.id, b"jpeg-bytes", filename="storefront.jpg", media_type="image/jpeg"
    )

    assert updated.before_image is not None
    assert updated.before_image.source is BeforeImageSource.MANUAL_UPLOAD
    assert artifact_store.stored_bytes == [
        (b"jpeg-bytes", project.id, "storefront.jpg", "image/jpeg")
    ]
    assert repository.projects[project.id].before_image is not None


async def test_replaces_an_existing_auto_picked_image():
    from makeover_discovery.domain.model.project import BeforeImage

    project = make_project(
        before_image=BeforeImage(
            uri="https://old.example/photo.jpg", source=BeforeImageSource.AUTO_PHOTO
        )
    )
    repository = FakeProjectRepository((project,))
    use_case = UploadBeforeImage(repository, FakeArtifactStore())

    updated = await use_case.execute(
        project.id, b"new-bytes", filename="new.jpg", media_type="image/jpeg"
    )

    assert updated.before_image is not None
    assert updated.before_image.source is BeforeImageSource.MANUAL_UPLOAD

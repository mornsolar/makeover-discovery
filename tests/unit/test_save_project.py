"""``SaveProject``, against fake storage."""

from __future__ import annotations

import pytest

from makeover_discovery.application.use_cases.save_project import SaveProject
from makeover_discovery.domain.errors import UpstreamError
from makeover_discovery.domain.model.pipeline import PipelineOutcome
from tests.fakes.artifact_store import FakeArtifactStore
from tests.fakes.brief import make_profile
from tests.fakes.clock import FixedClock
from tests.fakes.project import make_pipeline_result
from tests.fakes.project_repository import FakeProjectRepository
from tests.fakes.render_client import FAKE_ARTIFACT_BYTES, FakeRenderClient


def build() -> tuple[SaveProject, FakeProjectRepository, FakeArtifactStore, FakeRenderClient]:
    repository = FakeProjectRepository()
    artifact_store = FakeArtifactStore()
    render_client = FakeRenderClient()
    use_case = SaveProject(repository, artifact_store, FixedClock(), render_client)
    return use_case, repository, artifact_store, render_client


async def test_copies_every_artifact_into_the_artifact_store():
    use_case, _repository, artifact_store, _render_client = build()
    result = make_pipeline_result()

    await use_case.execute(result)

    filenames = {filename for _data, _pid, filename, _media_type in artifact_store.stored_bytes}
    assert filenames == {"scene.glb", "animation.mp4", "thumbnail.png"}


async def test_fetches_every_artifact_from_the_render_service():
    # Repo B's uri is a path on its own API, not this process's disk - the
    # bytes only ever arrive over HTTP.
    use_case, _repository, _artifact_store, render_client = build()
    result = make_pipeline_result()

    await use_case.execute(result)

    assert render_client.fetched_artifacts == ["/out/gltf", "/out/video", "/out/thumbnail"]


async def test_stores_the_bytes_the_render_service_returned():
    use_case, _repository, artifact_store, _render_client = build()
    result = make_pipeline_result()

    await use_case.execute(result)

    assert all(
        data == FAKE_ARTIFACT_BYTES for data, _pid, _filename, _mt in artifact_store.stored_bytes
    )


async def test_rejects_an_artifact_whose_bytes_do_not_match_the_reported_hash():
    use_case, _repository, _artifact_store, render_client = build()
    render_client.fetch_artifact = _corrupting_fetch  # type: ignore[method-assign]
    result = make_pipeline_result()

    with pytest.raises(UpstreamError, match="sha256"):
        await use_case.execute(result)


async def _corrupting_fetch(uri: str) -> bytes:
    return b"not-what-the-job-record-promised"


async def test_persists_under_the_businesss_own_id():
    use_case, repository, _artifact_store, _render_client = build()
    result = make_pipeline_result()

    project = await use_case.execute(result)

    assert project.id == result.business.id
    assert repository.projects[result.business.id] is project


async def test_auto_picks_a_before_image_when_a_photo_exists():
    use_case, _repository, _artifact_store, _render_client = build()
    business = make_profile(photo_urls=("https://example.com/before.jpg",))
    result = make_pipeline_result(business)

    project = await use_case.execute(result)

    assert project.before_image is not None
    assert project.before_image.uri == "https://example.com/before.jpg"


async def test_leaves_before_image_unset_when_there_is_no_photo():
    use_case, _repository, _artifact_store, _render_client = build()
    result = make_pipeline_result()

    project = await use_case.execute(result)

    assert project.before_image is None


async def test_persists_a_failed_pipeline_result_too():
    # A failed attempt must stay visible rather than being silently dropped.
    use_case, repository, artifact_store, render_client = build()
    result = make_pipeline_result(outcome=PipelineOutcome.RENDER_FAILED)

    project = await use_case.execute(result)

    assert project.pipeline.outcome is PipelineOutcome.RENDER_FAILED
    assert repository.projects[project.id] is project
    assert artifact_store.stored_bytes == []
    assert render_client.fetched_artifacts == []

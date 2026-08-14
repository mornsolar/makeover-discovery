"""The ``/projects`` endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from makeover_discovery.application.use_cases.publish_project import PublishProject
from makeover_discovery.application.use_cases.save_project import SaveProject
from makeover_discovery.application.use_cases.takedown_project import TakedownProject
from makeover_discovery.application.use_cases.upload_before_image import UploadBeforeImage
from makeover_discovery.domain.model.discovery import DiscoveryQuery
from makeover_discovery.domain.model.pipeline import PipelineResult
from makeover_discovery.interfaces.api.app import create_app
from makeover_discovery.interfaces.api.deps import (
    provide_project_repository,
    provide_publish_project,
    provide_run_makeover_pipeline,
    provide_save_project,
    provide_takedown_project,
    provide_upload_before_image,
)
from tests.fakes.artifact_store import FakeArtifactStore
from tests.fakes.clock import FixedClock
from tests.fakes.project import make_pipeline_result, make_project
from tests.fakes.project_repository import FakeProjectRepository
from tests.fakes.render_client import FakeRenderClient

HTTP_OK = 200
HTTP_CREATED = 201
HTTP_NOT_FOUND = 404
HTTP_UNPROCESSABLE = 422

POSTCODE_PAYLOAD = {"postcode": {"value": "50450", "country": "MY"}}


class _ScriptedPipeline:
    def __init__(self, results: tuple[PipelineResult, ...]) -> None:
        self._results = results

    async def execute(self, query: DiscoveryQuery) -> tuple[PipelineResult, ...]:
        return self._results


def client_for(
    repository: FakeProjectRepository | None = None,
) -> tuple[TestClient, FakeProjectRepository]:
    repository = repository or FakeProjectRepository()
    artifact_store = FakeArtifactStore()
    app = create_app()
    app.dependency_overrides[provide_project_repository] = lambda: repository
    app.dependency_overrides[provide_save_project] = lambda: SaveProject(
        repository, artifact_store, FixedClock(), FakeRenderClient()
    )
    app.dependency_overrides[provide_publish_project] = lambda: PublishProject(repository)
    app.dependency_overrides[provide_takedown_project] = lambda: TakedownProject(repository)
    app.dependency_overrides[provide_upload_before_image] = lambda: UploadBeforeImage(
        repository, artifact_store
    )
    app.dependency_overrides[provide_run_makeover_pipeline] = lambda: _ScriptedPipeline(
        (make_pipeline_result(),)
    )
    return TestClient(app), repository


class TestCreateProjects:
    def test_runs_the_pipeline_and_saves_each_result(self):
        client, repository = client_for()

        response = client.post("/projects", json=POSTCODE_PAYLOAD)

        assert response.status_code == HTTP_OK
        body = response.json()
        assert len(body) == 1
        assert body[0]["outcome"] == "rendered"
        assert len(repository.projects) == 1


class TestGetProject:
    def test_returns_a_saved_project(self):
        project = make_project()
        client, _repository = client_for(FakeProjectRepository((project,)))

        response = client.get(f"/projects/{project.id}")

        assert response.status_code == HTTP_OK
        assert response.json()["id"] == project.id

    def test_returns_404_for_an_unknown_project(self):
        client, _repository = client_for()

        assert client.get("/projects/does-not-exist").status_code == HTTP_NOT_FOUND


class TestPublish:
    def test_publishes_a_project_with_a_before_image(self):
        from makeover_discovery.domain.model.project import BeforeImage, BeforeImageSource

        project = make_project(
            before_image=BeforeImage(uri="https://x/img.jpg", source=BeforeImageSource.AUTO_PHOTO)
        )
        client, repository = client_for(FakeProjectRepository((project,)))

        response = client.post(f"/projects/{project.id}/publish")

        assert response.status_code == HTTP_OK
        assert response.json()["published"] is True
        assert repository.projects[project.id].published is True

    def test_refuses_to_publish_without_a_before_image(self):
        project = make_project(before_image=None)
        client, _repository = client_for(FakeProjectRepository((project,)))

        response = client.post(f"/projects/{project.id}/publish")

        assert response.status_code == HTTP_UNPROCESSABLE


class TestTakedown:
    def test_hard_disables_a_project(self):
        project = make_project(published=True)
        client, repository = client_for(FakeProjectRepository((project,)))

        response = client.post(f"/projects/{project.id}/takedown")

        assert response.status_code == HTTP_OK
        assert response.json()["takedown"] is True
        assert repository.projects[project.id].published is False


class TestBeforeImageUpload:
    def test_stores_the_upload_and_marks_it_manual(self):
        project = make_project(before_image=None)
        client, repository = client_for(FakeProjectRepository((project,)))

        response = client.post(
            f"/projects/{project.id}/before-image",
            files={"file": ("before.jpg", b"jpeg-bytes", "image/jpeg")},
        )

        assert response.status_code == HTTP_OK
        assert response.json()["before_image"]["source"] == "manual_upload"
        assert repository.projects[project.id].before_image is not None

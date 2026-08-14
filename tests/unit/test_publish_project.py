"""``PublishProject``, against a fake repository."""

from __future__ import annotations

import pytest

from makeover_discovery.application.use_cases.publish_project import PublishProject
from makeover_discovery.domain.errors import NotFoundError, ValidationError
from makeover_discovery.domain.model.pipeline import PipelineOutcome
from makeover_discovery.domain.model.project import BeforeImage, BeforeImageSource
from tests.fakes.project import make_project
from tests.fakes.project_repository import FakeProjectRepository

BEFORE = BeforeImage(uri="https://example.com/before.jpg", source=BeforeImageSource.AUTO_PHOTO)


async def test_raises_for_an_unknown_project():
    use_case = PublishProject(FakeProjectRepository())

    with pytest.raises(NotFoundError):
        await use_case.execute("does-not-exist")


async def test_publishes_a_rendered_project_with_a_before_image():
    project = make_project(before_image=BEFORE)
    repository = FakeProjectRepository((project,))
    use_case = PublishProject(repository)

    published = await use_case.execute(project.id)

    assert published.published is True
    assert repository.projects[project.id].published is True


async def test_refuses_to_publish_without_a_before_image():
    project = make_project(before_image=None)
    use_case = PublishProject(FakeProjectRepository((project,)))

    with pytest.raises(ValidationError, match="before-image"):
        await use_case.execute(project.id)


async def test_refuses_to_publish_a_failed_render():
    project = make_project(outcome=PipelineOutcome.RENDER_FAILED, before_image=BEFORE)
    use_case = PublishProject(FakeProjectRepository((project,)))

    with pytest.raises(ValidationError, match="no successful render"):
        await use_case.execute(project.id)


async def test_refuses_to_publish_over_an_active_takedown():
    project = make_project(before_image=BEFORE, takedown=True)
    use_case = PublishProject(FakeProjectRepository((project,)))

    with pytest.raises(ValidationError, match="taken down"):
        await use_case.execute(project.id)

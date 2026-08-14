"""``TakedownProject``, against a fake repository."""

from __future__ import annotations

import pytest

from makeover_discovery.application.use_cases.takedown_project import TakedownProject
from makeover_discovery.domain.errors import NotFoundError
from tests.fakes.project import make_project
from tests.fakes.project_repository import FakeProjectRepository


async def test_raises_for_an_unknown_project():
    use_case = TakedownProject(FakeProjectRepository())

    with pytest.raises(NotFoundError):
        await use_case.execute("does-not-exist")


async def test_hard_disables_a_published_project():
    project = make_project(published=True)
    repository = FakeProjectRepository((project,))
    use_case = TakedownProject(repository)

    updated = await use_case.execute(project.id)

    assert updated.takedown is True
    assert updated.published is False
    assert repository.projects[project.id].takedown is True

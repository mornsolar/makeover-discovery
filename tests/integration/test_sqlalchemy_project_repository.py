"""``SqlAlchemyProjectRepository``, against a real in-memory SQLite engine."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from makeover_discovery.domain.model.pipeline import PipelineOutcome
from makeover_discovery.domain.model.project import BeforeImage, BeforeImageSource
from makeover_discovery.infrastructure.persistence.engine import init_db
from makeover_discovery.infrastructure.persistence.sqlalchemy_project_repository import (
    SqlAlchemyProjectRepository,
)
from tests.fakes.project import make_project


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine("sqlite+aiosqlite://")
    await init_db(engine)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
def repository(engine: AsyncEngine) -> SqlAlchemyProjectRepository:
    return SqlAlchemyProjectRepository(async_sessionmaker(engine, expire_on_commit=False))


async def test_a_project_that_was_never_saved_is_absent(repository: SqlAlchemyProjectRepository):
    assert await repository.get("does-not-exist") is None


async def test_round_trips_a_rendered_project(repository: SqlAlchemyProjectRepository):
    project = make_project(
        before_image=BeforeImage(
            uri="https://example.com/before.jpg",
            source=BeforeImageSource.AUTO_PHOTO,
            attribution="© OpenStreetMap contributors",
        ),
        published=True,
    )

    await repository.save(project)
    loaded = await repository.get(project.id)

    assert loaded is not None
    assert loaded.id == project.id
    assert loaded.published is True
    assert loaded.pipeline.outcome is PipelineOutcome.RENDERED
    assert loaded.pipeline.business.name.value == project.pipeline.business.name.value
    assert loaded.pipeline.brief is not None
    assert loaded.pipeline.scene_spec is not None
    assert loaded.pipeline.render_job is not None
    assert loaded.before_image is not None
    assert loaded.before_image.uri == "https://example.com/before.jpg"
    assert loaded.before_image.attribution == "© OpenStreetMap contributors"


async def test_round_trips_a_failed_project_with_no_optional_fields(
    repository: SqlAlchemyProjectRepository,
):
    project = make_project(outcome=PipelineOutcome.BRIEF_FAILED)

    await repository.save(project)
    loaded = await repository.get(project.id)

    assert loaded is not None
    assert loaded.pipeline.outcome is PipelineOutcome.BRIEF_FAILED
    assert loaded.pipeline.brief is None
    assert loaded.pipeline.render_job is None
    assert loaded.before_image is None


async def test_save_upserts_rather_than_duplicates(repository: SqlAlchemyProjectRepository):
    project = make_project()
    await repository.save(project)

    republished = make_project(business=project.pipeline.business, published=True)
    await repository.save(republished)

    loaded = await repository.get(project.id)
    assert loaded is not None
    assert loaded.published is True

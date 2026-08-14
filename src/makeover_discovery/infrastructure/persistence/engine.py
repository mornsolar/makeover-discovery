"""Async SQLAlchemy engine lifecycle.

No Alembic: this phase creates the first and only table, and a migration
tool's value is in migrating a schema forward under existing data - premature
ahead of a second schema version. ``init_db`` is idempotent and safe to call
on every startup, the same thing tests do against an in-memory engine.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from makeover_discovery.infrastructure.persistence.models import Base


def create_db_engine(database_url: str) -> AsyncEngine:
    _ensure_sqlite_directory_exists(database_url)
    return create_async_engine(database_url)


def _ensure_sqlite_directory_exists(database_url: str) -> None:
    # SQLite opens the file itself but never creates a missing parent
    # directory - a fresh checkout's var/ doesn't exist until something
    # makes it, the same reason LocalFsArtifactStore does this for its
    # own project directories.
    url = make_url(database_url)
    if not url.drivername.startswith("sqlite"):
        return
    database = url.database
    if not database or database == ":memory:":
        return
    Path(database).parent.mkdir(parents=True, exist_ok=True)


async def init_db(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

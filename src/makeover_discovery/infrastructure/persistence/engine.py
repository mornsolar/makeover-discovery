"""Async SQLAlchemy engine lifecycle.

No Alembic: this phase creates the first and only table, and a migration
tool's value is in migrating a schema forward under existing data - premature
ahead of a second schema version. ``init_db`` is idempotent and safe to call
on every startup, the same thing tests do against an in-memory engine.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from makeover_discovery.infrastructure.persistence.models import Base


def create_db_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url)


async def init_db(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

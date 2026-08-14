"""``create_db_engine``'s directory-creation guard for file-based SQLite."""

from __future__ import annotations

from makeover_discovery.infrastructure.persistence.engine import create_db_engine, init_db


async def test_creates_a_missing_parent_directory_for_a_file_database(tmp_path):
    db_path = tmp_path / "nested" / "does" / "not" / "exist" / "makeover.db"
    engine = create_db_engine(f"sqlite+aiosqlite:///{db_path}")

    try:
        await init_db(engine)
        assert db_path.exists()
    finally:
        await engine.dispose()


async def test_an_in_memory_database_needs_no_directory():
    engine = create_db_engine("sqlite+aiosqlite://")

    try:
        await init_db(engine)
    finally:
        await engine.dispose()

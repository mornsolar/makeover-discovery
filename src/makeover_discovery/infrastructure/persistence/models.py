"""SQLAlchemy 2.0 mapping for the ``projects`` table.

One table, JSON text columns for the embedded ``BusinessProfile``/
``DesignBrief``/``SceneSpec``/``RenderJob`` snapshots - they are already
validated pydantic models with their own schema; normalizing them into
separate columns or tables is speculative for a phase with no querying need
beyond "fetch a project by id".
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ProjectRow(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    business_json: Mapped[str]
    outcome: Mapped[str] = mapped_column(String(32))
    brief_json: Mapped[str | None]
    scene_spec_json: Mapped[str | None]
    render_job_json: Mapped[str | None]
    pipeline_error: Mapped[str | None]
    before_image_uri: Mapped[str | None]
    before_image_source: Mapped[str | None]
    before_image_attribution: Mapped[str | None]
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    takedown: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

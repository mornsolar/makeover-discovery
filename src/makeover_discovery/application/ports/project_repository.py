"""Project persistence port."""

from __future__ import annotations

from typing import Protocol

from makeover_discovery.domain.model.project import Project


class ProjectRepository(Protocol):
    """Persists and retrieves ``Project``s by id.

    ``save`` is an upsert: the pipeline is already deterministic per
    business, so a re-run is meant to replace the prior project record for
    that business rather than accumulate duplicates.
    """

    async def save(self, project: Project) -> None: ...

    async def get(self, project_id: str) -> Project | None: ...

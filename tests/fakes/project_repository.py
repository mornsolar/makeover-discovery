"""In-memory ``ProjectRepository`` double."""

from __future__ import annotations

from makeover_discovery.domain.model.project import Project


class FakeProjectRepository:
    def __init__(self, projects: tuple[Project, ...] = ()) -> None:
        self.projects: dict[str, Project] = {p.id: p for p in projects}

    async def save(self, project: Project) -> None:
        self.projects[project.id] = project

    async def get(self, project_id: str) -> Project | None:
        return self.projects.get(project_id)

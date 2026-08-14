"""Landing-page rendering port."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from makeover_discovery.domain.model.project import Project


class LandingPageBuilder(Protocol):
    """Writes one project's static page (plus its assets) into ``out_dir``.

    Idempotent and safe to call again for the same project: a caller re-runs
    it after publishing or taking a project down, so the on-disk page
    reflects the project's current state rather than the state it was first
    written in.
    """

    async def build(self, project: Project, out_dir: Path) -> Path: ...

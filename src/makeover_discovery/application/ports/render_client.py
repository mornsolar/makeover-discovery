"""Render-job port."""

from __future__ import annotations

from typing import Protocol

from makeover_contracts.jobs import RenderJob
from makeover_contracts.scene import SceneSpec


class RenderClient(Protocol):
    """Submits a ``SceneSpec`` to Repo B and reports back on the job.

    Behind this port sits an HTTP call to Repo B's ``POST /jobs`` /
    ``GET /jobs/{id}`` - the one place this repo's dependency on the render
    service becomes a live network call rather than a compiled-in manifest.
    """

    async def submit(self, spec: SceneSpec) -> RenderJob: ...

    async def poll(self, job_id: str) -> RenderJob: ...

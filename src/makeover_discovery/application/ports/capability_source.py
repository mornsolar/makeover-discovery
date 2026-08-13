"""Renderer-capability port."""

from __future__ import annotations

from typing import Protocol

from makeover_contracts.capability import CapabilityManifest


class CapabilitySource(Protocol):
    """Supplies what the renderer can currently do.

    Behind this port sits either a live ``GET /capabilities`` call to Repo B or
    the manifest compiled into this build. Both are legitimate: until the render
    service is deployed there is nothing to ask.
    """

    async def manifest(self) -> CapabilityManifest: ...

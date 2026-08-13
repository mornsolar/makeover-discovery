"""Reads the renderer's vocabulary from its own ``GET /capabilities``.

This is the one-way arrow that avoids a circular dependency: Repo A learns what
Repo B can do by asking it, and Repo B never learns what a business is.
"""

from __future__ import annotations

from typing import Any, Final

from makeover_contracts.capability import CapabilityManifest
from pydantic import ValidationError

from makeover_discovery.domain.errors import UpstreamError
from makeover_discovery.infrastructure.http.cached_client import CachedHttpClient

RATE_KEY: Final = "render_service"
CAPABILITIES_PATH: Final = "/capabilities"


class HttpCapabilitySource:
    """Fetches and validates the live ``CapabilityManifest``."""

    def __init__(self, http: CachedHttpClient, *, base_url: str) -> None:
        self._http = http
        self._base_url = base_url.rstrip("/")

    async def manifest(self) -> CapabilityManifest:
        payload = await self._http.get_json(
            f"{self._base_url}{CAPABILITIES_PATH}", {}, rate_key=RATE_KEY
        )
        return _to_manifest(payload)


def _to_manifest(payload: Any) -> CapabilityManifest:
    try:
        return CapabilityManifest.model_validate(payload)
    except ValidationError as exc:
        # A manifest this repository cannot parse is worse than no manifest: it
        # would silently narrow or widen what the model is allowed to ask for.
        raise UpstreamError(f"the render service published an unusable manifest: {exc}") from exc

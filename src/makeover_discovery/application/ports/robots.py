"""robots.txt port."""

from __future__ import annotations

from typing import Protocol


class RobotsPolicy(Protocol):
    """Decides whether we are permitted to fetch a URL."""

    async def is_allowed(self, url: str) -> bool:
        """Whether this crawler may fetch ``url`` under the host's robots.txt."""
        ...

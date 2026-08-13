"""Outbound rate-limiting port.

Not optional polish: the Nominatim and Overpass usage policies cap unauthenticated
clients at roughly one request per second, and exceeding that gets an IP banned
rather than throttled. Every outbound provider call passes through here.
"""

from __future__ import annotations

from typing import Protocol


class RateLimiter(Protocol):
    """Delays the caller until the named resource may be used again."""

    async def acquire(self, key: str) -> None:
        """Block until a request against ``key`` is permitted."""
        ...

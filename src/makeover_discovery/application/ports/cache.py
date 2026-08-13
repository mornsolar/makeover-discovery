"""Response cache port.

Values are opaque strings - raw provider payloads - so the cache stays ignorant
of what it holds and can be swapped for Redis without touching any adapter.
"""

from __future__ import annotations

from typing import Protocol


class ResponseCache(Protocol):
    """A time-limited key/value store for upstream responses."""

    async def get(self, key: str) -> str | None:
        """Return the cached value, or ``None`` if absent or expired."""
        ...

    async def set(self, key: str, value: str, ttl_s: float) -> None:
        """Store ``value`` under ``key`` for ``ttl_s`` seconds."""
        ...

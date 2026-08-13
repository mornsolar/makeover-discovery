"""No-op rate limiter.

Used when replaying fixtures or pointing at a self-hosted provider, where the
public usage policy does not apply.
"""

from __future__ import annotations


class NullRateLimiter:
    """Permits every call immediately."""

    async def acquire(self, key: str) -> None:
        return None

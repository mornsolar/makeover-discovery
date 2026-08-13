"""Rate-limiter fakes."""

from __future__ import annotations


class RecordingRateLimiter:
    """Permits every call but remembers which resources were throttled.

    Lets a test assert that an adapter went through the limiter at all, which
    is the part that matters for usage-policy compliance.
    """

    def __init__(self) -> None:
        self.keys: list[str] = []

    async def acquire(self, key: str) -> None:
        self.keys.append(key)

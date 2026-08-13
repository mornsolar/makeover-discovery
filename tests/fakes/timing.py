"""Controllable time sources for the rate limiter and cache.

Real sleeping in a test suite is a tax paid on every run forever, so the clock
is advanced by hand instead.
"""

from __future__ import annotations


class ManualClock:
    """A monotonic clock that only moves when told to."""

    def __init__(self, start: float = 0.0) -> None:
        self.value = start
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds

    async def sleep(self, seconds: float) -> None:
        """Record the requested delay and jump the clock forward by it."""
        self.sleeps.append(seconds)
        self.value += seconds

"""Deterministic ``Clock`` used across the suite."""

from __future__ import annotations

from datetime import UTC, datetime


class FixedClock:
    """Returns a fixed instant, so time-dependent assertions are exact."""

    def __init__(self, instant: datetime | None = None) -> None:
        self._instant = instant or datetime(2026, 8, 13, 9, 30, tzinfo=UTC)

    def now(self) -> datetime:
        return self._instant

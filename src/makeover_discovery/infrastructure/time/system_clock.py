"""Wall-clock implementation of the ``Clock`` port."""

from __future__ import annotations

from datetime import UTC, datetime


class SystemClock:
    """Reads the host clock. The only place in the app that may do so."""

    def now(self) -> datetime:
        return datetime.now(tz=UTC)

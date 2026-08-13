"""Time port.

Time is injected rather than read from the ambient environment so that retention
windows, cache expiry, and job timing are all testable without sleeping.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    """Supplies the current instant."""

    def now(self) -> datetime:
        """Return the current timezone-aware UTC instant."""
        ...

"""In-process TTL cache.

Enough for a single worker; the ``ResponseCache`` port exists so Phase 7 can
swap in Redis once there is more than one process to share hits between.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

DEFAULT_MAX_ENTRIES: Final = 512


@dataclass(frozen=True)
class _Entry:
    value: str
    expires_at: float


class InMemoryTTLCache:
    """Bounded, least-recently-used cache with per-entry expiry.

    Bounded on purpose: an unbounded cache keyed by user-supplied postcodes is
    a memory-exhaustion vector, not just a tidiness concern.
    """

    def __init__(
        self,
        *,
        max_entries: int = DEFAULT_MAX_ENTRIES,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be at least 1")
        self._max_entries = max_entries
        self._monotonic = monotonic
        self._entries: dict[str, _Entry] = {}

    async def get(self, key: str) -> str | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        if self._monotonic() >= entry.expires_at:
            del self._entries[key]
            return None
        # Re-insert to move the key to the most-recent end of the dict, which
        # preserves insertion order and so doubles as the LRU queue.
        del self._entries[key]
        self._entries[key] = entry
        return entry.value

    async def set(self, key: str, value: str, ttl_s: float) -> None:
        if ttl_s <= 0:
            return
        self._entries.pop(key, None)
        self._entries[key] = _Entry(value=value, expires_at=self._monotonic() + ttl_s)
        while len(self._entries) > self._max_entries:
            oldest = next(iter(self._entries))
            del self._entries[oldest]

    def __len__(self) -> int:
        return len(self._entries)

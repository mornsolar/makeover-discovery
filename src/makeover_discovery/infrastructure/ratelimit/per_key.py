"""Minimum-interval rate limiter.

A token bucket would allow bursts, which is exactly what Nominatim's usage
policy forbids. This enforces a hard floor on the gap between consecutive
requests to the same resource instead.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Mapping

Monotonic = Callable[[], float]
Sleeper = Callable[[float], Awaitable[None]]


class PerKeyRateLimiter:
    """Serialises calls per key, spacing them by at least ``interval``.

    ``monotonic`` and ``sleep`` are injected so tests can assert on the delays
    requested without spending real seconds waiting for them.
    """

    def __init__(
        self,
        *,
        default_interval_s: float,
        intervals: Mapping[str, float] | None = None,
        monotonic: Monotonic = time.monotonic,
        sleep: Sleeper = asyncio.sleep,
    ) -> None:
        self._default_interval_s = default_interval_s
        self._intervals = dict(intervals or {})
        self._monotonic = monotonic
        self._sleep = sleep
        self._locks: dict[str, asyncio.Lock] = {}
        self._next_allowed: dict[str, float] = {}

    def _lock_for(self, key: str) -> asyncio.Lock:
        # Safe without its own guard: creating the lock never awaits, so no
        # other coroutine can interleave between the lookup and the insert.
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        return lock

    async def acquire(self, key: str) -> None:
        interval = self._intervals.get(key, self._default_interval_s)
        if interval <= 0:
            return

        async with self._lock_for(key):
            now = self._monotonic()
            earliest = self._next_allowed.get(key)
            if earliest is not None and earliest > now:
                await self._sleep(earliest - now)
                # Advance from the scheduled instant, not from "now": measuring
                # after the sleep would let scheduler jitter accumulate into
                # ever-widening gaps over a long crawl.
                self._next_allowed[key] = earliest + interval
                return
            self._next_allowed[key] = now + interval

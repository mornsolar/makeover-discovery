"""Minimum-interval rate limiter."""

from __future__ import annotations

import pytest

from makeover_discovery.infrastructure.ratelimit.null import NullRateLimiter
from makeover_discovery.infrastructure.ratelimit.per_key import PerKeyRateLimiter
from tests.fakes.timing import ManualClock

INTERVAL_S = 1.0


@pytest.fixture
def clock():
    return ManualClock()


def build(clock: ManualClock, **kwargs) -> PerKeyRateLimiter:
    return PerKeyRateLimiter(
        default_interval_s=INTERVAL_S,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
        **kwargs,
    )


async def test_permits_the_first_call_without_waiting(clock):
    await build(clock).acquire("nominatim")

    assert clock.sleeps == []


async def test_delays_a_second_call_by_the_full_interval(clock):
    limiter = build(clock)

    await limiter.acquire("nominatim")
    await limiter.acquire("nominatim")

    assert clock.sleeps == [INTERVAL_S]


async def test_does_not_delay_a_call_that_is_already_late(clock):
    limiter = build(clock)
    await limiter.acquire("nominatim")
    clock.advance(INTERVAL_S * 3)

    await limiter.acquire("nominatim")

    assert clock.sleeps == []


async def test_spaces_a_burst_evenly_without_drifting(clock):
    limiter = build(clock)

    for _ in range(3):
        await limiter.acquire("nominatim")

    # Each wait is exactly one interval: the limiter schedules from the last
    # permitted slot rather than re-reading the clock after sleeping, so
    # scheduler jitter cannot accumulate.
    assert clock.sleeps == [INTERVAL_S, INTERVAL_S]


async def test_tracks_each_resource_separately(clock):
    limiter = build(clock)

    await limiter.acquire("nominatim")
    await limiter.acquire("overpass")

    assert clock.sleeps == []


async def test_honours_a_per_key_interval_override(clock):
    limiter = build(clock, intervals={"overpass": 5.0})

    await limiter.acquire("overpass")
    await limiter.acquire("overpass")

    assert clock.sleeps == [5.0]


async def test_disables_throttling_for_a_zero_interval(clock):
    limiter = build(clock, intervals={"local": 0.0})

    await limiter.acquire("local")
    await limiter.acquire("local")

    assert clock.sleeps == []


async def test_null_limiter_never_waits():
    limiter = NullRateLimiter()

    assert await limiter.acquire("anything") is None

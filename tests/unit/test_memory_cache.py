"""In-process TTL cache."""

from __future__ import annotations

import pytest

from makeover_discovery.infrastructure.cache.memory import InMemoryTTLCache
from tests.fakes.timing import ManualClock

TTL_S = 60.0


@pytest.fixture
def clock():
    return ManualClock()


async def test_returns_a_value_that_was_stored(clock):
    cache = InMemoryTTLCache(monotonic=clock.monotonic)

    await cache.set("key", "payload", TTL_S)

    assert await cache.get("key") == "payload"


async def test_returns_none_for_an_unknown_key(clock):
    cache = InMemoryTTLCache(monotonic=clock.monotonic)

    assert await cache.get("missing") is None


async def test_forgets_a_value_once_its_ttl_elapses(clock):
    cache = InMemoryTTLCache(monotonic=clock.monotonic)
    await cache.set("key", "payload", TTL_S)

    clock.advance(TTL_S)

    assert await cache.get("key") is None
    assert len(cache) == 0


async def test_declines_to_store_a_non_positive_ttl(clock):
    cache = InMemoryTTLCache(monotonic=clock.monotonic)

    await cache.set("key", "payload", 0.0)

    assert await cache.get("key") is None


async def test_evicts_the_least_recently_used_entry_when_full(clock):
    cache = InMemoryTTLCache(max_entries=2, monotonic=clock.monotonic)
    await cache.set("a", "1", TTL_S)
    await cache.set("b", "2", TTL_S)

    await cache.get("a")
    await cache.set("c", "3", TTL_S)

    assert await cache.get("b") is None
    assert await cache.get("a") == "1"
    assert await cache.get("c") == "3"


async def test_overwrites_rather_than_duplicating_a_key(clock):
    cache = InMemoryTTLCache(monotonic=clock.monotonic)

    await cache.set("key", "first", TTL_S)
    await cache.set("key", "second", TTL_S)

    assert await cache.get("key") == "second"
    assert len(cache) == 1


def test_rejects_a_cache_that_cannot_hold_anything():
    with pytest.raises(ValueError, match="max_entries"):
        InMemoryTTLCache(max_entries=0)

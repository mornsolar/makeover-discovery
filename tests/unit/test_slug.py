"""Business slug generation."""

from __future__ import annotations

import re

from makeover_discovery.domain.model.slug import MAX_SLUG_CHARS, to_slug

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")


def test_produces_a_readable_slug():
    assert to_slug("Kedai Kopi Ali", "node/1").startswith("kedai-kopi-ali-")


def test_matches_the_contract_slug_pattern():
    assert SLUG_PATTERN.match(to_slug("Kedai Kopi Ali!! ~~", "node/1"))


def test_distinguishes_two_branches_of_the_same_chain():
    # Same name, different OSM object: without the fingerprint the second
    # branch would silently overwrite the first's artifacts.
    assert to_slug("7-Eleven", "node/1") != to_slug("7-Eleven", "node/2")


def test_is_stable_for_the_same_input():
    assert to_slug("7-Eleven", "node/1") == to_slug("7-Eleven", "node/1")


def test_stays_within_the_contract_length_limit():
    slug = to_slug("A Very Long Restaurant Name " * 10, "node/1")

    assert len(slug) <= MAX_SLUG_CHARS
    assert SLUG_PATTERN.match(slug)


def test_falls_back_when_the_name_has_no_usable_characters():
    slug = to_slug("!!! ~~~", "node/1")

    assert slug.startswith("business-")
    assert SLUG_PATTERN.match(slug)

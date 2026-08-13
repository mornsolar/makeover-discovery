"""Candidate de-duplication."""

from __future__ import annotations

from makeover_discovery.domain.model.dedupe import deduplicate
from tests.fakes.candidates import make_candidate


def test_collapses_the_same_business_mapped_as_node_and_way():
    node = make_candidate(external_id="node/1")
    way = make_candidate(external_id="way/2")

    assert deduplicate([node, way]) == (node,)


def test_keeps_the_first_occurrence():
    first = make_candidate(external_id="node/1", address_line="Jalan Ampang")
    second = make_candidate(external_id="way/2", address_line=None)

    assert deduplicate([first, second])[0].address_line == "Jalan Ampang"


def test_ignores_case_and_spacing_differences_in_names():
    original = make_candidate(external_id="node/1", name="Kedai Kopi Ali")
    variant = make_candidate(external_id="node/2", name="  kedai  kopi ALI ")

    assert deduplicate([original, variant]) == (original,)


def test_keeps_same_named_businesses_at_different_locations():
    branch_one = make_candidate(external_id="node/1", lat=3.1600)
    branch_two = make_candidate(external_id="node/2", lat=3.1800)

    assert len(deduplicate([branch_one, branch_two])) == 2


def test_returns_empty_for_no_candidates():
    assert deduplicate([]) == ()

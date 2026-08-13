"""Google Places type taxonomy."""

from __future__ import annotations

from makeover_contracts.business import BusinessCategory

from makeover_discovery.infrastructure.directory.places_taxonomy import (
    classify,
    included_types_for,
)


def test_classifies_a_place_by_its_primary_type():
    assert classify(["cafe", "food"]) is BusinessCategory.CAFE


def test_prefers_the_more_specific_rule_regardless_of_list_order():
    # Places does not guarantee ordering beyond primaryType-first; the rule
    # table's own order breaks the tie, not the response's.
    assert classify(["store", "bakery"]) is BusinessCategory.BAKERY


def test_returns_none_for_a_type_we_do_not_handle():
    assert classify(["parking"]) is None


def test_returns_none_for_an_empty_type_list():
    assert classify([]) is None


def test_selects_every_rule_when_no_category_is_requested():
    types = included_types_for(())

    assert "cafe" in types
    assert "store" in types


def test_narrows_to_the_types_for_the_requested_category():
    assert included_types_for((BusinessCategory.CAFE,)) == ("cafe", "coffee_shop")


def test_covers_multiple_requested_categories_without_duplicates():
    types = included_types_for((BusinessCategory.CAFE, BusinessCategory.BAKERY))

    assert types == ("cafe", "coffee_shop", "bakery")

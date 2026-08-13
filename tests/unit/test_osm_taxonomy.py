"""OpenStreetMap tag taxonomy."""

from __future__ import annotations

from makeover_contracts.business import BusinessCategory

from makeover_discovery.infrastructure.directory.osm_taxonomy import classify, selectors_for


def test_classifies_a_specific_tag_before_the_catch_all():
    assert classify({"shop": "bakery"}) is BusinessCategory.BAKERY


def test_falls_back_to_retail_for_any_other_shop():
    assert classify({"shop": "clothes"}) is BusinessCategory.RETAIL


def test_classifies_a_valueless_rule_by_key_alone():
    assert classify({"craft": "carpenter"}) is BusinessCategory.WORKSHOP


def test_returns_none_for_something_that_is_not_a_business():
    assert classify({"amenity": "bus_station"}) is None


def test_returns_none_for_untagged_features():
    assert classify({}) is None


def test_selects_every_rule_when_no_category_is_requested():
    selectors = selectors_for(())

    assert '["amenity"="cafe"]' in selectors
    assert '["shop"]' in selectors


def test_drops_specific_shop_rules_when_the_catch_all_is_present():
    selectors = selectors_for(())

    assert '["shop"="bakery"]' not in selectors


def test_narrows_to_the_requested_category():
    assert selectors_for((BusinessCategory.CAFE,)) == ('["amenity"="cafe"]',)


def test_keeps_specific_rules_when_the_catch_all_is_not_requested():
    selectors = selectors_for((BusinessCategory.BAKERY,))

    assert selectors == ('["shop"="bakery"]', '["shop"="pastry"]')


def test_collapses_overlapping_categories_to_the_broader_selector():
    selectors = selectors_for((BusinessCategory.RETAIL, BusinessCategory.BAKERY))

    assert selectors == ('["shop"]',)

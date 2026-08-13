"""Mapping between OpenStreetMap tags and our business categories.

One ordered rule table serves both directions - building the Overpass query and
classifying what comes back - so a new category can never be searchable but
unclassifiable, or vice versa.

Order matters: rules are consulted top to bottom, so specific tags must precede
the catch-alls that would otherwise swallow them.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from makeover_contracts.business import BusinessCategory


@dataclass(frozen=True)
class OsmRule:
    """One tag pattern and the category it implies."""

    key: str
    value: str | None
    category: BusinessCategory

    @property
    def selector(self) -> str:
        """The rule as an Overpass tag filter, e.g. ``["amenity"="cafe"]``."""
        if self.value is None:
            return f'["{self.key}"]'
        return f'["{self.key}"="{self.value}"]'

    def matches(self, tags: Mapping[str, str]) -> bool:
        present = tags.get(self.key)
        if present is None:
            return False
        return self.value is None or present == self.value


OSM_RULES: Final[tuple[OsmRule, ...]] = (
    OsmRule("amenity", "restaurant", BusinessCategory.RESTAURANT),
    OsmRule("amenity", "fast_food", BusinessCategory.RESTAURANT),
    OsmRule("amenity", "food_court", BusinessCategory.RESTAURANT),
    OsmRule("amenity", "cafe", BusinessCategory.CAFE),
    OsmRule("shop", "bakery", BusinessCategory.BAKERY),
    OsmRule("shop", "pastry", BusinessCategory.BAKERY),
    OsmRule("amenity", "bar", BusinessCategory.BAR),
    OsmRule("amenity", "pub", BusinessCategory.BAR),
    OsmRule("shop", "hairdresser", BusinessCategory.SALON),
    OsmRule("shop", "beauty", BusinessCategory.SALON),
    OsmRule("shop", "massage", BusinessCategory.SALON),
    OsmRule("amenity", "clinic", BusinessCategory.CLINIC),
    OsmRule("amenity", "doctors", BusinessCategory.CLINIC),
    OsmRule("amenity", "dentist", BusinessCategory.CLINIC),
    OsmRule("tourism", "hotel", BusinessCategory.HOTEL),
    OsmRule("tourism", "guest_house", BusinessCategory.HOTEL),
    OsmRule("tourism", "hostel", BusinessCategory.HOTEL),
    OsmRule("shop", "car_repair", BusinessCategory.WORKSHOP),
    OsmRule("craft", None, BusinessCategory.WORKSHOP),
    OsmRule("shop", None, BusinessCategory.RETAIL),
)


def classify(tags: Mapping[str, str]) -> BusinessCategory | None:
    """Return the category these tags imply, or ``None`` if we do not handle it.

    ``None`` rather than ``BusinessCategory.OTHER``: an unclassified feature is
    something to drop, and returning a real category would smuggle post boxes
    and bus stops into a list of businesses.
    """
    for rule in OSM_RULES:
        if rule.matches(tags):
            return rule.category
    return None


def selectors_for(categories: Sequence[BusinessCategory]) -> tuple[str, ...]:
    """Overpass tag filters covering ``categories``; empty means every rule.

    When a catch-all rule for a key is included, the specific rules for that
    same key are dropped: they are a strict subset, and emitting both makes the
    generated query twice as long for identical results.
    """
    rules = OSM_RULES if not categories else _rules_for(categories)
    catch_all_keys = {rule.key for rule in rules if rule.value is None}
    kept = (rule for rule in rules if rule.value is None or rule.key not in catch_all_keys)
    return tuple(dict.fromkeys(rule.selector for rule in kept))


def _rules_for(categories: Iterable[BusinessCategory]) -> tuple[OsmRule, ...]:
    wanted = set(categories)
    return tuple(rule for rule in OSM_RULES if rule.category in wanted)
